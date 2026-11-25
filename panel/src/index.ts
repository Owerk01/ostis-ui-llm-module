/** Публичный API панели ассистента. */

export { AssistantPanel } from './AssistantPanel'
export type { AssistantPanelProps } from './AssistantPanel'

export { ScMemoryTransport, DEFAULT_SC_URL } from './transport/scMemory'
export { DirectHttpTransport, DEFAULT_BASE_URL } from './transport/directHttp'
export {
  AssistantBusy,
  AssistantCancelled,
  AssistantDialogNotFound,
  AssistantSchemaMissing,
  AssistantTimeout,
  ASSISTANT_BUSY_ERROR,
  ASSISTANT_CANCELLED_ERROR,
  ASSISTANT_DIALOG_NOT_FOUND_ERROR,
  ASSISTANT_SCHEMA_MISSING_ERROR,
  ASSISTANT_TIMEOUT_ERROR,
} from './transport/errors.ts'
export { DialogNotFoundError, DIALOG_NOT_FOUND_ERROR } from './transport/types'
export type {
  AskOptions,
  DialogContextMode,
  DialogContextOptions,
  AssistantHealth,
  AssistantMessage,
  AssistantRole,
  AssistantTransport,
  MessageState,
  OutcomeCode,
  SourceRef,
} from './transport/types'
