/**
 * Контракт транспорта панели (AGENTS.md 3.12).
 *
 * Панель не знает, откуда приходит ответ: из sc-памяти (боевой режим)
 * или по HTTP (отладочный). Оба транспорта обязаны реализовать этот интерфейс.
 */

export type AssistantRole = 'user' | 'assistant'
export type MessageState = 'pending' | 'streaming' | 'done' | 'error' | 'cancelled'

export interface SourceRef {
  idtf: string
  labelRu?: string
  scAddr?: number
}

export interface AssistantMessage {
  id: string
  role: AssistantRole
  text: string
  state: MessageState
  createdAt: string // ISO-8601
  sources?: SourceRef[]
  error?: string
  scAddr?: number
}

export interface AssistantHealth {
  llm: { backend: string; model: string; reachable: boolean }
  kb: { connected: boolean; knowledgeSource: 'kb' | 'fallback'; packVersion: string }
}

export interface AssistantTransport {
  readonly kind: 'direct-http' | 'sc-memory'
  health(): Promise<AssistantHealth>
  ensureDialog(): Promise<string> // id диалога
  history(dialogId: string): Promise<AssistantMessage[]>
  ask(
    dialogId: string,
    question: string,
    onDelta?: (chunk: string) => void,
    signal?: AbortSignal,
  ): Promise<AssistantMessage>
  cancel(messageId: string): Promise<void>
}
