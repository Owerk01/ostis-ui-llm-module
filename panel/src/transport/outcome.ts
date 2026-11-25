/**
 * Коды исхода сообщений и правило «Повторить».
 *
 * Список совпадает с `contract/identifiers.json` и `sc/outcomes.py`.
 * Редактор не хардкодит коды: transports заполняют `code` и `retryable`.
 */

export const OUTCOME_CODES = [
  'ok',
  'busy',
  'llm_unavailable',
  'llm_timeout',
  'invalid_request',
  'cancelled',
  'agent_restarted',
  'schema_missing',
  'schema_mismatch',
  'dialog_not_found',
  'internal',
] as const

export const PENDING_CODE = 'pending'
export const DEFAULT_CODE = 'ok'

export type OutcomeCode = (typeof OUTCOME_CODES)[number] | typeof PENDING_CODE

const MESSAGE_CODES: ReadonlySet<string> = new Set([...OUTCOME_CODES, PENDING_CODE])

// Временные ошибки: повтор вопроса без изменения текста имеет смысл.
const RETRYABLE_CODES: ReadonlySet<OutcomeCode> = new Set<OutcomeCode>([
  'busy',
  'llm_unavailable',
  'llm_timeout',
  'agent_restarted',
  'internal',
])

export function toOutcomeCode(value: unknown, fallback: OutcomeCode = DEFAULT_CODE): OutcomeCode {
  return typeof value === 'string' && MESSAGE_CODES.has(value)
    ? (value as OutcomeCode)
    : fallback
}

export function isRetryable(code: OutcomeCode): boolean {
  return RETRYABLE_CODES.has(code)
}

/** Код из типизированной/сетевой ошибки; неизвестная ошибка — internal. */
export function outcomeCodeFromError(error: unknown): OutcomeCode {
  if (error && typeof error === 'object' && 'code' in error) {
    return toOutcomeCode((error as { code: unknown }).code, 'internal')
  }
  return 'internal'
}

export interface CodedError extends Error {
  code: OutcomeCode
}

export function codedError(message: string, code: OutcomeCode): CodedError {
  const error = new Error(message) as CodedError
  error.code = code
  return error
}
