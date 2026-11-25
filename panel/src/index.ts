/** Публичный API панели ассистента. */

export { AssistantPanel } from './AssistantPanel'
export type { AssistantPanelProps } from './AssistantPanel'

export { ScMemoryTransport, DEFAULT_SC_URL } from './transport/scMemory'
export { DirectHttpTransport, DEFAULT_BASE_URL } from './transport/directHttp'
export { DialogNotFoundError, DIALOG_NOT_FOUND_ERROR } from './transport/types'
export type {
  AssistantHealth,
  AssistantMessage,
  AssistantRole,
  AssistantTransport,
  MessageState,
  OutcomeCode,
  SourceRef,
} from './transport/types'
