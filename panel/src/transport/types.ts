/**
 * Контракт транспорта панели.
 *
 * Панель не знает, откуда приходит ответ: из sc-памяти (боевой режим)
 * или по HTTP (отладочный). Оба транспорта обязаны реализовать этот интерфейс.
 */

import type { OutcomeCode } from './outcome.ts'

export type AssistantRole = 'user' | 'assistant'
export type MessageState = 'pending' | 'streaming' | 'done' | 'error' | 'cancelled'

export type { OutcomeCode } from './outcome.ts'

export interface SourceRef {
  idtf: string
  labelRu?: string
  scAddr?: number
}

export type KnowledgeSource = 'kb' | 'fallback' | 'unknown'

export interface AssistantMessage {
  id: string
  role: AssistantRole
  text: string
  state: MessageState
  createdAt: string // ISO-8601
  /**
   * Код исхода. У assistant всегда заполнен: `pending` до ответа, один из
   * OUTCOME_CODES после; у старых сообщений без link — `ok`. У user — `ok`.
   */
  code: OutcomeCode
  /** Вычислено транспортом из `code`; редактор не знает список кодов. */
  retryable: boolean
  model?: string | null
  promptVersion?: string
  knowledgeSource?: KnowledgeSource
  sources?: SourceRef[]
  error?: string
  scAddr?: number
}

export interface AssistantHealth {
  llm: { backend: string; model: string | null; reachable: boolean }
  kb: { connected: boolean; knowledgeSource: KnowledgeSource; packVersion: string }
  /** Источник и состояние сервиса из узла состояния (sc-memory). */
  schemaLoaded?: boolean
  agentAlive?: boolean
  state?: string
  model?: string | null
  promptVersion?: string
  knowledgeSource?: KnowledgeSource
  packVersion?: string
  queueDepth?: number
  contractVersion?: string
  /** Фактические значения таймаутов: клиент ждёт дольше LLM. */
  timeouts?: { llmTimeoutS: number; dialogClientTimeoutS: number }
}

export interface AssistantTransport {
  readonly kind: 'direct-http' | 'sc-memory'
  health(): Promise<AssistantHealth>
  /**
   * Без аргумента создаёт новый диалог; с `dialogId` открывает существующий
   * (по `nrel_ui_id`). Невалидный/ненайденный id — типизированная ошибка
   * `DialogNotFoundError`, новый диалог не создаётся молча.
   */
  ensureDialog(dialogId?: string): Promise<string>
  history(dialogId: string): Promise<AssistantMessage[]>
  ask(
    dialogId: string,
    question: string,
    onDelta?: (chunk: string) => void,
    signal?: AbortSignal,
  ): Promise<AssistantMessage>
  cancel(messageId: string): Promise<void>
}

/** Код ошибки: диалог с переданным id не найден в БЗ. */
export const DIALOG_NOT_FOUND_ERROR = 'dialog_not_found'

/** Типизированная ошибка неизвестного диалога: `ask()` не должен подменять диалог. */
export class DialogNotFoundError extends Error {
  readonly code = DIALOG_NOT_FOUND_ERROR
  readonly dialogId: string

  constructor(dialogId: string) {
    super(`dialog_not_found: диалог ${dialogId} не найден`)
    this.name = 'DialogNotFoundError'
    this.dialogId = dialogId
  }
}
