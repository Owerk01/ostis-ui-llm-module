/** Приведение старой и новой форм вызова ask к одному объекту options. */

import type { AskOptions, AskOptionsArg } from './types.ts'

export function normalizeAskOptions(
  options?: AskOptionsArg,
  signal?: AbortSignal,
): AskOptions {
  if (typeof options === 'function') return { onDelta: options, signal }
  if (options) return { ...options, signal: options.signal ?? signal }
  return { signal }
}

/** Тело /ask direct-http: snake_case, как остальные поля API. */
export function contextPayload(options: AskOptions): Record<string, unknown> | undefined {
  const context = options.context
  if (!context || context.mode === 'none') return undefined
  const payload: Record<string, unknown> = { mode: context.mode }
  if (context.interfaceId) payload.interface_id = context.interfaceId
  if (context.componentIds?.length) payload.component_ids = context.componentIds
  return payload
}
