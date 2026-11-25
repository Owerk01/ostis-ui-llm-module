/**
 * Снимок узла состояния сервиса (`nrel_ui_service_state`) и проверка аренды.
 *
 * Вынесено из scMemory.ts, чтобы тестировать parsing/heartbeat в Node
 * (strip-режим не импортирует ts-sc-client) и не зависеть от БЗ в тестах.
 */

import type { KnowledgeSource } from './types.ts'

// Должен совпадать с `service_lease_ttl_s` в настройках сервиса.
export const SERVICE_LEASE_TTL_S = 20

export interface ServiceStateSnapshot {
  state?: string | null
  heartbeatAt?: string | null
  model?: string | null
  backend?: string | null
  promptVersion?: string | null
  packVersion?: string | null
  knowledgeSource?: KnowledgeSource | null
  contractVersion?: string | null
  queueSize?: number | null
}

/** JSON из sc-link → нормализованный снимок; null при отсутствии/битом JSON. */
export function parseServiceState(value: string | null): ServiceStateSnapshot | null {
  if (!value) return null
  try {
    const parsed: unknown = JSON.parse(value)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return null
    const raw = parsed as Record<string, unknown>
    const str = (key: string): string | null =>
      typeof raw[key] === 'string' ? (raw[key] as string) : null
    const source = raw.knowledge_source
    return {
      state: str('state'),
      heartbeatAt: str('heartbeat_at'),
      model: str('model'),
      backend: str('backend'),
      promptVersion: str('prompt_version'),
      packVersion: str('pack_version'),
      contractVersion: str('contract_version'),
      knowledgeSource: source === 'kb' || source === 'fallback' ? source : null,
      queueSize: typeof raw.queue_size === 'number' ? raw.queue_size : null,
    }
  } catch {
    return null
  }
}

/** Агент жив: heartbeat свежий и состояние не «stopped». */
export function serviceAlive(snapshot: ServiceStateSnapshot, nowMs: number = Date.now()): boolean {
  if (snapshot.state === 'stopped') return false
  const heartbeat = snapshot.heartbeatAt ? Date.parse(snapshot.heartbeatAt) : Number.NaN
  if (Number.isNaN(heartbeat)) return false
  const ageSeconds = (nowMs - heartbeat) / 1000
  return ageSeconds >= 0 && ageSeconds <= SERVICE_LEASE_TTL_S
}
