/**
 * Транспорт через sc-память.
 *
 * Панель создаёт узел действия, ждёт статус от sc-агента и читает историю
 * диалога из БЗ. HTTP к сервису не используется.
 *
 * Стриминга в этом режиме нет: ответ приходит одним куском после записи
 * в БЗ, поэтому onDelta вызывается один раз с полным текстом.
 */

import {
  ScAddr,
  ScClient,
  ScConstruction,
  ScEventSubscription,
  ScEventSubscriptionParams,
  ScEventType,
  ScHelper,
  ScLinkContent,
  ScLinkContentType,
  ScTemplate,
  ScType,
} from 'ts-sc-client'

import { normalizeAskOptions } from './askOptions.ts'
import { resolveClientTimeoutMs } from './timeout.ts'
import { AssistantBusy, AssistantSchemaMissing } from './errors.ts'
import { LateResult } from './lateResult.ts'
import { isRetryable, toOutcomeCode } from './outcome.ts'
import { parseServiceState, serviceAlive, type ServiceStateSnapshot } from './serviceHealth.ts'
import { findMessageInResult, type ResultRow } from './actionResult'
import { isStableDialogId, newDialogId } from './dialogId'
import { DialogNotFoundError } from './types'
import { healthFromMessages } from './health'
import type {
  AskOptionsArg,
  AssistantHealth,
  AssistantMessage,
  AssistantTransport,
  KnowledgeSource,
  DialogContextOptions,
  MessageState,
  SourceRef,
} from './types'

export const DEFAULT_SC_URL = 'ws://127.0.0.1:8090/ws_json'

const ACTION_CLASS = 'action_answer_ui_development_question'
const STATUS_ERROR = 'error'
// Клиентский таймаут ожидания ответа задаётся извне (см. clientTimeoutMs).
const POLL_INTERVAL_MS = 400

const MESSAGE_STATES: ReadonlySet<string> = new Set([
  'pending',
  'streaming',
  'done',
  'error',
  'cancelled',
])

function toState(value: string | null): MessageState {
  return value && MESSAGE_STATES.has(value) ? (value as MessageState) : 'done'
}

interface ActiveRequest {
  waiter: LateResult<AssistantMessage>
}

interface Keynodes {
  dialog: ScAddr
  userMessage: ScAddr
  assistantMessage: ScAddr
  action: ScAddr
  actionClass: ScAddr
  actionInitiated: ScAddr
  actionFinished: ScAddr
  rrel1: ScAddr
  rrel2: ScAddr
  rrel3: ScAddr | null
  contextClass: ScAddr | null
  nrelContextMode: ScAddr | null
  nrelContextInterface: ScAddr | null
  nrelContextComponent: ScAddr | null
  nrelDialogMessage: ScAddr
  nrelValue: ScAddr
  nrelTime: ScAddr
  nrelState: ScAddr
  nrelMessageCode: ScAddr | null
  nrelSource: ScAddr
  nrelModel: ScAddr
  nrelPromptVersion: ScAddr
  nrelKnowledgeSource: ScAddr
  nrelUiId: ScAddr
  service: ScAddr
  nrelUiServiceState: ScAddr
  nrelUiServiceHeartbeat: ScAddr
}

export class ScMemoryTransport implements AssistantTransport {
  readonly kind = 'sc-memory' as const

  private readonly client: ScClient
  private readonly helper: ScHelper
  private readonly clientTimeoutMs: number
  private keynodesCache: Keynodes | null = null
  private active: ActiveRequest | null = null
  private dialogId: string | null = null

  constructor(client: ScClient, clientTimeoutMs?: number) {
    this.client = client
    this.helper = new ScHelper(client)
    // Лимит берётся из переменной окружения сборки, fallback 35 с.
    this.clientTimeoutMs = resolveClientTimeoutMs(clientTimeoutMs)
  }

  async health(): Promise<AssistantHealth> {
    let connected = false
    let serviceSnapshot: ServiceStateSnapshot | null = null
    try {
      const k = await this.keynodes()
      connected = (await this.client.getElementsTypes([k.dialog])).length > 0
      serviceSnapshot = await this.readServiceState(k)
    } catch {
      connected = false
    }

    // Снимок сервиса — источник истины; без него (ошибка чтения) — fallback по истории.
    const derived = serviceSnapshot ? null : healthFromMessages([])
    const source: KnowledgeSource =
      serviceSnapshot?.knowledgeSource ?? derived?.knowledgeSource ?? 'unknown'
    const model = serviceSnapshot?.model ?? derived?.model ?? null
    const packVersion = serviceSnapshot?.packVersion ?? derived?.packVersion ?? ''

    let agentAlive = false
    let serviceState = 'starting'
    let queueDepth = 0
    if (serviceSnapshot) {
      agentAlive = serviceAlive(serviceSnapshot)
      serviceState = serviceSnapshot.state ?? 'starting'
      queueDepth = serviceSnapshot.queueSize ?? 0
    }

    return {
      llm: { backend: 'sc-memory', model, reachable: connected },
      kb: {
        connected,
        knowledgeSource: source,
        packVersion,
      },
      schemaLoaded: connected,
      agentAlive,
      state: serviceState,
      model,
      packVersion,
      promptVersion: serviceSnapshot?.promptVersion ?? undefined,
      knowledgeSource: source,
      queueDepth,
      contractVersion: serviceSnapshot?.contractVersion ?? '0.1.0',
    }
  }

  async ensureDialog(dialogId?: string): Promise<string> {
    const k = await this.keynodes()

    if (dialogId) {
      const existing = await this.findDialogById(dialogId, k)
      if (!existing) throw new DialogNotFoundError(dialogId)
      this.dialogId = dialogId
      return dialogId
    }

    if (this.dialogId) {
      const existing = await this.findDialogById(this.dialogId, k)
      if (existing) return this.dialogId
    }

    const dialog = await this.createNode()
    await this.instantiate(k.dialog, dialog)
    const id = newDialogId()
    await this.relateNonRole(dialog, await this.createLink(id), k.nrelUiId)
    this.dialogId = id
    return id
  }

  async history(dialogId: string): Promise<AssistantMessage[]> {
    const k = await this.keynodes()
    const dialog = await this.resolveDialog(dialogId, k)
    if (!dialog) return []

    const template = new ScTemplate()
    template.quintuple(
      dialog,
      ScType.VarCommonArc,
      [ScType.VarNode, '_message'],
      ScType.VarPermPosArc,
      k.nrelDialogMessage,
    )
    const rows = await this.client.searchByTemplate(template)

    const messages = await Promise.all(
      rows.map(async (row) => {
        const message = row.get('_message')
        const ordinal = await this.ordinal(dialog, message)
        return { ordinal, message: await this.readMessage(message, k) }
      }),
    )
    messages.sort((a, b) => a.ordinal - b.ordinal)
    return messages.map((item) => item.message)
  }

  async ask(
    dialogId: string,
    question: string,
    options?: AskOptionsArg,
    legacySignal?: AbortSignal,
  ): Promise<AssistantMessage> {
    const { onDelta, signal, context } = normalizeAskOptions(options, legacySignal)
    if (this.active) throw new Error('Предыдущий запрос ещё выполняется')

    const k = await this.keynodes()
    const dialog = await this.resolveDialog(dialogId, k)
    if (!dialog) throw new DialogNotFoundError(dialogId)
    this.dialogId = dialogId

    const action = await this.createAction(k, dialog, question, context)
    const actionId = String(action.value)
    const waiter = new LateResult<AssistantMessage>({
      actionId,
      dialogId,
      isFinished: () => this.isFinished(k, action),
      readResult: () => this.finishedMessage(k, action),
      pollIntervalMs: POLL_INTERVAL_MS,
    })
    const active: ActiveRequest = { waiter }
    this.active = active

    const onExternalAbort = () => waiter.wake()
    if (signal) {
      if (signal.aborted) onExternalAbort()
      else signal.addEventListener('abort', onExternalAbort, { once: true })
    }

    let subscription: Promise<ScEventSubscription> | null = null
    try {
      subscription = this.client
        .createElementaryEventSubscriptions(
          new ScEventSubscriptionParams(
            action,
            ScEventType.AfterGenerateIncomingArc,
            () => waiter.poke(),
          ),
        )
        .then((items) => items[0])

      const last = await waiter.wait(this.clientTimeoutMs)
      onDelta?.(last.text)
      if (last.code === 'busy') throw new AssistantBusy()
      if (last.state === 'error') return { ...last, error: last.text }
      return last
    } finally {
      signal?.removeEventListener('abort', onExternalAbort)
      if (this.active === active) this.active = null
      if (subscription) {
        void subscription
          .then((sub) => this.client.destroyElementaryEventSubscriptions(sub.id))
          .catch(() => undefined)
      }
    }
  }

  async cancel(_messageId: string): Promise<void> {
    // Мягкая отмена: перестаём ждать, но конструкции и сообщения в БЗ не трогаем.
    this.active?.waiter.wake()
  }

  async readActionResult(actionId: string): Promise<AssistantMessage | null> {
    const value = Number(actionId)
    const action = Number.isFinite(value) ? new ScAddr(value) : null
    if (!action || !action.isValid()) return null

    const k = await this.keynodes()
    const waiter = new LateResult<AssistantMessage>({
      actionId,
      isFinished: () => this.isFinished(k, action),
      readResult: () => this.finishedMessage(k, action),
      pollIntervalMs: POLL_INTERVAL_MS,
    })
    return waiter.readActionResult()
  }

  /** Готовое сообщение из результата действия; без повторной отправки вопроса. */
  private async finishedMessage(k: Keynodes, action: ScAddr): Promise<AssistantMessage | null> {
    const result = await this.helper.getResult(action)
    if (!result?.isValid()) return null

    const template = new ScTemplate()
    template.triple(result, ScType.VarPermPosArc, [ScType.Unknown, '_element'])
    const rows = (await this.client.searchByTemplate(template)) as unknown as ResultRow[]
    const messageAddr = await findMessageInResult(rows, async (addr) => {
      const assistantTemplate = new ScTemplate()
      assistantTemplate.triple(k.assistantMessage, ScType.VarPermPosArc, addr as ScAddr)
      return (await this.client.searchByTemplate(assistantTemplate)).length > 0
    })
    if (!messageAddr) return null
    return this.readMessage(messageAddr as ScAddr, k)
  }

  // --- создание конструкций ---

  private async createAction(
    k: Keynodes,
    dialog: ScAddr,
    question: string,
    context?: DialogContextOptions,
  ): Promise<ScAddr> {
    const action = await this.createNode()
    await this.instantiate(k.action, action)
    await this.instantiate(k.actionClass, action)

    const questionLink = await this.createLink(question)
    await this.relateRole(action, questionLink, k.rrel1)
    await this.relateRole(action, dialog, k.rrel2)
    if (context && context.mode !== 'none') await this.attachContext(k, action, context)

    const construction = new ScConstruction()
    construction.generateConnector(ScType.ConstPermPosArc, k.actionInitiated, action)
    await this.client.generateElements(construction)
    return action
  }

  /** rrel_3 → concept_ui_dialog_context; none не требует новой схемы в БЗ. */
  private async attachContext(
    k: Keynodes,
    action: ScAddr,
    context: DialogContextOptions,
  ): Promise<void> {
    if (
      !k.rrel3 ||
      !k.contextClass ||
      !k.nrelContextMode ||
      !k.nrelContextInterface ||
      !k.nrelContextComponent
    ) {
      // Не подменять контекст молча: без схемы T7 запрос не может быть выполнен.
      throw new Error('Схема контекста ассистента не загружена в БЗ. Выполните make kb-load')
    }
    const node = await this.createNode()
    await this.instantiate(k.contextClass, node)
    await this.relateNonRole(node, await this.createLink(context.mode), k.nrelContextMode)

    if (context.interfaceId) {
      const interfaceNode = await this.findNodeById(context.interfaceId, k)
      if (!interfaceNode) throw new Error(`Интерфейс ${context.interfaceId} не найден в БЗ`)
      await this.relateNonRole(node, interfaceNode, k.nrelContextInterface)
    }
    for (const id of context.componentIds ?? []) {
      const component = await this.findNodeById(id, k)
      if (!component) throw new Error(`Компонент ${id} не найден в БЗ`)
      await this.relateNonRole(node, component, k.nrelContextComponent)
    }
    await this.relateRole(action, node, k.rrel3)
  }

  private async createNode(): Promise<ScAddr> {
    const construction = new ScConstruction()
    construction.generateNode(ScType.ConstNode, '_node')
    const [node] = await this.client.generateElements(construction)
    return node
  }

  private async createLink(text: string): Promise<ScAddr> {
    const construction = new ScConstruction()
    construction.generateLink(
      ScType.ConstNodeLink,
      new ScLinkContent(text, ScLinkContentType.String),
      '_link',
    )
    const [link] = await this.client.generateElements(construction)
    return link
  }

  private async instantiate(classAddr: ScAddr, node: ScAddr): Promise<void> {
    const construction = new ScConstruction()
    construction.generateConnector(ScType.ConstPermPosArc, classAddr, node)
    await this.client.generateElements(construction)
  }

  /**
   * Ролевая связь (`rrel_1`, `rrel_2`).
   *
   * py-sc-kpm ищет аргументы действия шаблоном `src --VAR_PERM_POS_ARC--> элемент`,
   * поэтому основная дуга роли должна быть perm-pos, а не common arc
   * (common arc используется только для `nrel_*`).
   */
  private async relateRole(source: ScAddr, target: ScAddr, relation: ScAddr): Promise<void> {
    const construction = new ScConstruction()
    construction.generateConnector(ScType.ConstPermPosArc, source, target, '_arc')
    construction.generateConnector(ScType.ConstPermPosArc, relation, '_arc')
    await this.client.generateElements(construction)
  }

  private async isFinished(k: Keynodes, action: ScAddr): Promise<boolean> {
    const template = new ScTemplate()
    template.triple(k.actionFinished, ScType.VarPermPosArc, action)
    return (await this.client.searchByTemplate(template)).length > 0
  }

  // --- чтение ---

  private async readMessage(message: ScAddr, k: Keynodes): Promise<AssistantMessage> {
    const role = await this.role(message, k)
    const text = (await this.linkValue(message, k.nrelValue)) ?? ''
    const stateValue = await this.linkValue(message, k.nrelState)
    const state = toState(stateValue)
    const rawCode = k.nrelMessageCode
      ? await this.linkValue(message, k.nrelMessageCode)
      : null
    const code = toOutcomeCode(rawCode)
    const createdAt = (await this.linkValue(message, k.nrelTime)) ?? ''
    const model = await this.linkValue(message, k.nrelModel)
    const promptVersion = await this.linkValue(message, k.nrelPromptVersion)
    const rawSource = await this.linkValue(message, k.nrelKnowledgeSource)
    const knowledgeSource =
      rawSource === 'kb' || rawSource === 'fallback' ? rawSource : 'unknown'

    return {
      id: String(message.value),
      role,
      text,
      state,
      createdAt,
      code,
      retryable: isRetryable(code),
      model,
      promptVersion: promptVersion ?? undefined,
      knowledgeSource,
      sources: await this.sources(message, k),
      error: state === STATUS_ERROR ? text : undefined,
      scAddr: message.value,
    }
  }

  private async role(message: ScAddr, k: Keynodes): Promise<'user' | 'assistant'> {
    const template = new ScTemplate()
    template.triple(k.userMessage, ScType.VarPermPosArc, message)
    if ((await this.client.searchByTemplate(template)).length > 0) return 'user'
    return 'assistant'
  }

  private async ordinal(dialog: ScAddr, message: ScAddr): Promise<number> {
    const template = new ScTemplate()
    template.quintuple(
      dialog,
      ScType.VarCommonArc,
      message,
      ScType.VarPermPosArc,
      [ScType.VarNodeRole, '_rrel'],
    )
    const rows = await this.client.searchByTemplate(template)
    if (rows.length === 0) return 0
    const idtf = await this.helper.getSystemIdentifier(rows[0].get('_rrel'))
    const value = Number.parseInt(idtf?.split('_').pop() ?? '', 10)
    return Number.isFinite(value) ? value : 0
  }

  private async sources(message: ScAddr, k: Keynodes): Promise<SourceRef[]> {
    const template = new ScTemplate()
    template.quintuple(
      message,
      ScType.VarCommonArc,
      [ScType.VarNode, '_source'],
      ScType.VarPermPosArc,
      k.nrelSource,
    )
    const rows = await this.client.searchByTemplate(template)
    const result: SourceRef[] = []
    for (const row of rows) {
      const addr = row.get('_source')
      const idtf = await this.helper.getSystemIdentifier(addr)
      if (idtf) result.push({ idtf, scAddr: addr.value })
    }
    return result
  }

  private async linkValue(node: ScAddr, relation: ScAddr): Promise<string | null> {
    const template = new ScTemplate()
    template.quintuple(
      node,
      ScType.VarCommonArc,
      [ScType.VarNodeLink, '_link'],
      ScType.VarPermPosArc,
      relation,
    )
    const rows = await this.client.searchByTemplate(template)
    if (rows.length === 0) return null
    const contents = await this.client.getLinkContents([rows[0].get('_link')])
    const data = contents[0]?.data
    return data === undefined ? null : String(data)
  }

  // --- служебное ---

  /** Узел по nrel_ui_id; используется для интерфейса и компонентов контекста. */
  private async findNodeById(id: string, k: Keynodes): Promise<ScAddr | null> {
    const groups = await this.client.searchLinksByContents([id])
    for (const link of groups.flat()) {
      const template = new ScTemplate()
      template.quintuple(
        [ScType.VarNode, '_node'],
        ScType.VarCommonArc,
        link,
        ScType.VarPermPosArc,
        k.nrelUiId,
      )
      const rows = await this.client.searchByTemplate(template)
      if (rows.length) return rows[0].get('_node')
    }
    return null
  }

  private async findDialogById(id: string, k: Keynodes): Promise<ScAddr | null> {
    if (!isStableDialogId(id)) return null
    const groups = await this.client.searchLinksByContents([id])
    for (const link of groups.flat()) {
      const template = new ScTemplate()
      template.quintuple(
        [ScType.VarNode, '_dialog'],
        ScType.VarCommonArc,
        link,
        ScType.VarPermPosArc,
        k.nrelUiId,
      )
      const rows = await this.client.searchByTemplate(template)
      if (rows.length) return rows[0].get('_dialog')
    }
    return null
  }

  private async resolveDialog(dialogId: string, k: Keynodes): Promise<ScAddr | null> {
    return this.findDialogById(dialogId, k)
  }

  private async relateNonRole(source: ScAddr, target: ScAddr, relation: ScAddr): Promise<void> {
    const construction = new ScConstruction()
    construction.generateConnector(ScType.ConstCommonArc, source, target, '_arc')
    construction.generateConnector(ScType.ConstPermPosArc, relation, '_arc')
    await this.client.generateElements(construction)
  }

  private async keynodes(): Promise<Keynodes> {
    if (this.keynodesCache) return this.keynodesCache

    const classes = [
      'concept_ui_dialog',
      'concept_ui_user_message',
      'concept_ui_assistant_message',
      'action',
      ACTION_CLASS,
      'action_initiated',
      'action_finished',
      'concept_ui_dialog_service',
    ] as const
    const relations = [
      'nrel_ui_dialog_message',
      'nrel_ui_value',
      'nrel_ui_message_time',
      'nrel_ui_message_state',
      'nrel_ui_message_code',
      'nrel_ui_answer_source',
      'nrel_ui_llm_model',
      'nrel_ui_prompt_version',
      'nrel_ui_knowledge_source',
      'nrel_ui_id',
      'nrel_ui_service_state',
      'nrel_ui_service_heartbeat',
    ] as const

    // Невалидный тип = поиск без создания. С валидным типом resolveKeynodes
    // создал бы отсутствующий узел в БЗ, чего read-путь делать не должен.
    const searchOnly = new ScType()
    const resolved = await this.client.resolveKeynodes([
      ...classes.map((id) => ({ id, type: searchOnly })),
      ...relations.map((id) => ({ id, type: searchOnly })),
      { id: 'rrel_1', type: searchOnly },
      { id: 'rrel_2', type: searchOnly },
      { id: 'rrel_3', type: searchOnly },
      { id: 'concept_ui_dialog_context', type: searchOnly },
      { id: 'nrel_ui_context_mode', type: searchOnly },
      { id: 'nrel_ui_context_interface', type: searchOnly },
      { id: 'nrel_ui_context_component', type: searchOnly },
    ])
    // Код исхода и контекст опциональны в старой БЗ: none работает без них.
    const optional = new Set([
      'nrel_ui_message_code',
      'rrel_3',
      'concept_ui_dialog_context',
      'nrel_ui_context_mode',
      'nrel_ui_context_interface',
      'nrel_ui_context_component',
    ])
    const missing = Object.entries(resolved)
      .filter(([id, addr]) => !addr.isValid() && !optional.has(id))
      .map(([id]) => id)
    if (missing.length) {
      throw new AssistantSchemaMissing(missing)
    }

    this.keynodesCache = {
      dialog: resolved.concept_ui_dialog,
      userMessage: resolved.concept_ui_user_message,
      assistantMessage: resolved.concept_ui_assistant_message,
      action: resolved.action,
      actionClass: resolved[ACTION_CLASS],
      actionInitiated: resolved.action_initiated,
      actionFinished: resolved.action_finished,
      rrel1: resolved.rrel_1,
      rrel2: resolved.rrel_2,
      rrel3: resolved.rrel_3?.isValid() ? resolved.rrel_3 : null,
      contextClass: resolved['concept_ui_dialog_context']?.isValid()
        ? resolved['concept_ui_dialog_context']
        : null,
      nrelContextMode: resolved['nrel_ui_context_mode']?.isValid()
        ? resolved['nrel_ui_context_mode']
        : null,
      nrelContextInterface: resolved['nrel_ui_context_interface']?.isValid()
        ? resolved['nrel_ui_context_interface']
        : null,
      nrelContextComponent: resolved['nrel_ui_context_component']?.isValid()
        ? resolved['nrel_ui_context_component']
        : null,
      nrelDialogMessage: resolved.nrel_ui_dialog_message,
      nrelValue: resolved.nrel_ui_value,
      nrelTime: resolved.nrel_ui_message_time,
      nrelState: resolved.nrel_ui_message_state,
      nrelMessageCode: resolved['nrel_ui_message_code']?.isValid()
        ? resolved['nrel_ui_message_code']
        : null,
      nrelSource: resolved.nrel_ui_answer_source,
      nrelModel: resolved.nrel_ui_llm_model,
      nrelPromptVersion: resolved.nrel_ui_prompt_version,
      nrelKnowledgeSource: resolved.nrel_ui_knowledge_source,
      nrelUiId: resolved.nrel_ui_id,
      service: resolved['concept_ui_dialog_service'],
      nrelUiServiceState: resolved['nrel_ui_service_state'],
      nrelUiServiceHeartbeat: resolved['nrel_ui_service_heartbeat'],
    }
    return this.keynodesCache
  }

  /**
   * Снимок узла состояния сервиса (B0-2): JSON из link `nrel_ui_service_state`.
   * Возвращает null, если узел или связь не найдены — вызывающий держит fallback.
   */
  private async readServiceState(k: Keynodes): Promise<ServiceStateSnapshot | null> {
    const value = await this.linkValue(k.service, k.nrelUiServiceState)
    return parseServiceState(value)
  }
}
