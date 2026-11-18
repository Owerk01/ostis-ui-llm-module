/** Таймер индикации обработки: одна база времени, без отрицательных значений. */

export const MAX_ELAPSED_MS = 180_000 // таймаут ожидания ответа в scMemory.ts

export function formatElapsed(ms: number): string {
  const safe = Number.isFinite(ms) ? Math.min(Math.max(ms, 0), MAX_ELAPSED_MS) : 0
  const seconds = Math.floor(safe / 1000)
  const tenths = Math.floor((safe % 1000) / 100)
  return `${seconds},${tenths} с`
}
