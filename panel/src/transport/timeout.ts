/**
 * Разрешение клиентского таймаута ожидания ответа.
 *
 * Приоритет: явно переданный clientTimeoutMs > переменная сборки
 * VITE_DIALOG_CLIENT_TIMEOUT_S > значение по умолчанию 35 с.
 * Константа 30 с из редактора больше не жёстко закодирована.
 */

const DEFAULT_CLIENT_TIMEOUT_MS = 35_000

export function resolveClientTimeoutMs(clientTimeoutMs?: number): number {
  const envTimeoutMs =
    typeof import.meta.env?.VITE_DIALOG_CLIENT_TIMEOUT_S === 'string'
      ? Number.parseInt(import.meta.env.VITE_DIALOG_CLIENT_TIMEOUT_S, 10)
      : undefined
  const resolved = clientTimeoutMs ?? envTimeoutMs ?? DEFAULT_CLIENT_TIMEOUT_MS
  return Number.isFinite(resolved) && resolved > 0 ? resolved : DEFAULT_CLIENT_TIMEOUT_MS
}
