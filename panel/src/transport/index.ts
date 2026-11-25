/**
 * Публичный API транспорта диалога без React.
 *
 * Этот entry собирается отдельно (`npm run build:transport`) и не импортирует
 * AssistantPanel, CSS-модули или React. Единственная внешняя зависимость —
 * `ts-sc-client` (peerDependency).
 */

export { ScMemoryTransport, DEFAULT_SC_URL } from './scMemory'
export { ScClient } from './scClientApi'
export { DirectHttpTransport, DEFAULT_BASE_URL } from './directHttp'

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
  transportErrorFromCode,
} from './errors'
export { DialogNotFoundError, DIALOG_NOT_FOUND_ERROR } from './types'

export {
  DEFAULT_CODE,
  OUTCOME_CODES,
  PENDING_CODE,
  isRetryable,
  outcomeCodeFromError,
  toOutcomeCode,
} from './outcome'
export { isStableDialogId, newDialogId } from './dialogId'
export { CONTRACT_VERSION } from './contract'

export type { AskOptions, AskOptionsArg, KnowledgeSource } from './types'
export type { CodedError } from './outcome'
export type {
  AssistantHealth,
  AssistantMessage,
  AssistantRole,
  AssistantTransport,
  DialogContextMode,
  DialogContextOptions,
  MessageState,
  OutcomeCode,
  SourceRef,
} from './types'
