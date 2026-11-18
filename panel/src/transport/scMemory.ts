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
  ScEventSubscriptionParams,
  ScEventType,
  ScHelper,
  ScLinkContent,
  ScLinkContentType,
  ScTemplate,
  ScType,
} from 'ts-sc-client'

import { healthFromMessages } from './health'
import type {
  AssistantHealth,
  AssistantMessage,
  AssistantTransport,
  MessageState,
  SourceRef,
} from './types'

export const DEFAULT_SC_URL = 'ws://127.0.0.1:8090/ws_json'

const ACTION_CLASS = 'action_answer_ui_development_question'
const STATUS_ERROR = 'error'
const ACTION_TIMEOUT_MS = 180_000
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
  action: ScAddr | null
  cancelled: boolean
  wake?: () => void
}

interface Keynodes {
  dialog: ScAddr
  userMessage: ScAddr
  action: ScAddr
  actionClass: ScAddr
  actionInitiated: ScAddr
  actionFinished: ScAddr
  rrel1: ScAddr
  rrel2: ScAddr
  nrelDialogMessage: ScAddr
  nrelValue: ScAddr
  nrelTime: ScAddr
  nrelState: ScAddr
  nrelSource: ScAddr
  nrelModel: ScAddr
  nrelPromptVersion: ScAddr
  nrelKnowledgeSource: ScAddr
}

export class ScMemoryTransport implements AssistantTransport {
  readonly kind = 'sc-memory' as const

  private readonly client: ScClient
  private readonly helper: ScHelper
  private keynodesCache: Keynodes | null = null
  private active: ActiveRequest | null = null
  private dialogId: string | null = null

  constructor(client: ScClient) {
    this.client = client
    this.helper = new ScHelper(client)
  }

  async health(): Promise<AssistantHealth> {
    let connected = false
    try {
      const k = await this.keynodes()
      connected = (await this.client.getElementsTypes([k.dialog])).length > 0
    } catch {
      connected = false
    }
    let derived = healthFromMessages([])
    if (connected && this.dialogId) {
      try {
        derived = healthFromMessages(await this.history(this.dialogId))
      } catch {
        // История может быть ещё пустой — остаёмся в unknown.
      }
    }
    return {
      llm: { backend: 'sc-memory', model: derived.model, reachable: connected },
      kb: {
        connected,
        knowledgeSource: derived.knowledgeSource,
        packVersion: derived.packVersion,
      },
    }
  }

  async ensureDialog(): Promise<string> {
    const k = await this.keynodes()
    const dialog = await this.createNode()
    await this.instantiate(k.dialog, dialog)
    this.dialogId = String(dialog.value)
    return this.dialogId
  }

  async history(dialogId: string): Promise<AssistantMessage[]> {
    const dialog = this.toAddr(dialogId)
    if (!dialog.isValid()) return []

    const k = await this.keynodes()
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
    onDelta?: (chunk: string) => void,
    signal?: AbortSignal,
  ): Promise<AssistantMessage> {
    if (this.active) throw new Error('Предыдущий запрос ещё выполняется')

    const k = await this.keynodes()
    let dialog = this.toAddr(dialogId)
    if (!dialog.isValid()) {
      dialog = await this.createNode()
      await this.instantiate(k.dialog, dialog)
    }
    this.dialogId = String(dialog.value)

    const action = await this.createAction(k, dialog, question)
    const active: ActiveRequest = { action, cancelled: false }
    this.active = active

    const onExternalAbort = () => {
      active.cancelled = true
      active.wake?.()
    }
    if (signal) {
      if (signal.aborted) onExternalAbort()
      else signal.addEventListener('abort', onExternalAbort, { once: true })
    }

    try {
      const finished = await this.waitForFinish(action, active)
      if (active.cancelled) {
        return {
          id: String(action.value),
          role: 'assistant',
          text: '',
          state: 'cancelled',
          createdAt: new Date().toISOString(),
        }
      }
      if (!finished) throw new Error('Превышено время ожидания ответа')

      const history = await this.history(String(dialog.value))
      const last = [...history].reverse().find((message) => message.role === 'assistant')
      if (!last) throw new Error('Агент завершил действие, но ответа в БЗ нет')

      onDelta?.(last.text)
      if (last.state === 'error') {
        return { ...last, error: last.text }
      }
      return last
    } finally {
      signal?.removeEventListener('abort', onExternalAbort)
      if (this.active === active) this.active = null
    }
  }

  async cancel(_messageId: string): Promise<void> {
    if (!this.active) return
    // Мягкая отмена: панель перестаёт ждать, агент допишет ответ в БЗ.
    this.active.cancelled = true
    this.active.wake?.()
  }

  // --- создание конструкций ---

  private async createAction(
    k: Keynodes,
    dialog: ScAddr,
    question: string,
  ): Promise<ScAddr> {
    const action = await this.createNode()
    await this.instantiate(k.action, action)
    await this.instantiate(k.actionClass, action)

    const questionLink = await this.createLink(question)
    await this.relateRole(action, questionLink, k.rrel1)
    await this.relateRole(action, dialog, k.rrel2)

    const construction = new ScConstruction()
    construction.generateConnector(ScType.ConstPermPosArc, k.actionInitiated, action)
    await this.client.generateElements(construction)
    return action
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

  // --- ожидание результата ---

  private async waitForFinish(action: ScAddr, active: ActiveRequest): Promise<boolean> {
    const k = await this.keynodes()
    let settled = false

    return new Promise<boolean>((resolve) => {
      const finish = (result: boolean) => {
        if (settled) return
        settled = true
        window.clearInterval(timer)
        window.clearTimeout(timeout)
        active.wake = undefined
        void subscription.then((sub) =>
          this.client.destroyElementaryEventSubscriptions(sub.id).catch(() => undefined),
        )
        resolve(result)
      }

      const check = async () => {
        if (settled) return
        if (active.cancelled) {
          finish(false)
          return
        }
        try {
          if (await this.isFinished(k, action)) finish(true)
        } catch {
          // временная ошибка соединения — повторим на следующем тике
        }
      }

      const subscription = this.client
        .createElementaryEventSubscriptions(
          new ScEventSubscriptionParams(action, ScEventType.AfterGenerateIncomingArc, () => {
            void check()
          }),
        )
        .then((items) => items[0])

      const timer = window.setInterval(() => void check(), POLL_INTERVAL_MS)
      const timeout = window.setTimeout(() => finish(false), ACTION_TIMEOUT_MS)
      active.wake = () => finish(false)
      void check()
    })
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

  private toAddr(dialogId: string): ScAddr {
    const value = Number(dialogId)
    return new ScAddr(Number.isFinite(value) ? value : 0)
  }

  private async keynodes(): Promise<Keynodes> {
    if (this.keynodesCache) return this.keynodesCache

    const classes = [
      'concept_ui_dialog',
      'concept_ui_user_message',
      'action',
      ACTION_CLASS,
      'action_initiated',
      'action_finished',
    ] as const
    const relations = [
      'nrel_ui_dialog_message',
      'nrel_ui_value',
      'nrel_ui_message_time',
      'nrel_ui_message_state',
      'nrel_ui_answer_source',
      'nrel_ui_llm_model',
      'nrel_ui_prompt_version',
      'nrel_ui_knowledge_source',
    ] as const

    // Невалидный тип = поиск без создания. С валидным типом resolveKeynodes
    // создал бы отсутствующий узел в БЗ, чего read-путь делать не должен.
    const searchOnly = new ScType()
    const resolved = await this.client.resolveKeynodes([
      ...classes.map((id) => ({ id, type: searchOnly })),
      ...relations.map((id) => ({ id, type: searchOnly })),
      { id: 'rrel_1', type: searchOnly },
      { id: 'rrel_2', type: searchOnly },
    ])
    const missing = Object.entries(resolved)
      .filter(([, addr]) => !addr.isValid())
      .map(([id]) => id)
    if (missing.length) {
      throw new Error(
        `Схема ассистента не загружена в БЗ: ${missing.join(', ')}. Выполните make kb-load`,
      )
    }

    this.keynodesCache = {
      dialog: resolved.concept_ui_dialog,
      userMessage: resolved.concept_ui_user_message,
      action: resolved.action,
      actionClass: resolved[ACTION_CLASS],
      actionInitiated: resolved.action_initiated,
      actionFinished: resolved.action_finished,
      rrel1: resolved.rrel_1,
      rrel2: resolved.rrel_2,
      nrelDialogMessage: resolved.nrel_ui_dialog_message,
      nrelValue: resolved.nrel_ui_value,
      nrelTime: resolved.nrel_ui_message_time,
      nrelState: resolved.nrel_ui_message_state,
      nrelSource: resolved.nrel_ui_answer_source,
      nrelModel: resolved.nrel_ui_llm_model,
      nrelPromptVersion: resolved.nrel_ui_prompt_version,
      nrelKnowledgeSource: resolved.nrel_ui_knowledge_source,
    }
    return this.keynodesCache
  }
}
