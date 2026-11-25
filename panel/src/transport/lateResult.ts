/**
 * Ожидание действия с возможностью дочитать поздний результат.
 *
 * Вынесено из scMemory.ts, чтобы сценарий «таймаут → readActionResult» можно
 * было тестировать без ts-sc-client (CommonJS-зависимости не грузятся в
 * node --experimental-strip-types).
 */

import { AssistantCancelled, AssistantTimeout } from './errors.ts'

export interface Clock {
  now(): number
  /** Возвращает функцию отмены таймера. */
  setTimer(delayMs: number, fn: () => void): () => void
}

export const systemClock: Clock = {
  now: () => Date.now(),
  setTimer: (delayMs, fn) => {
    const id = globalThis.setTimeout(fn, delayMs)
    return () => globalThis.clearTimeout(id)
  },
}

export interface LateResultDeps<T> {
  actionId: string
  dialogId?: string
  isFinished(): Promise<boolean>
  readResult(): Promise<T | null>
  clock?: Clock
  pollIntervalMs?: number
}

export class LateResult<T> {
  private readonly deps: LateResultDeps<T>
  private readonly clock: Clock
  private readonly pollIntervalMs: number
  private clearTimer: (() => void) | null = null
  private rejectWait: ((reason?: unknown) => void) | null = null
  private checkNow: (() => void) | null = null
  private settled = false
  private checking = false
  private earlyCancel: AssistantCancelled | null = null

  constructor(deps: LateResultDeps<T>) {
    this.deps = deps
    this.clock = deps.clock ?? systemClock
    this.pollIntervalMs = deps.pollIntervalMs ?? 400
  }

  /** Ждёт завершения; при истечении лимита бросает `AssistantTimeout`. */
  async wait(timeoutMs: number): Promise<T> {
    const deadline = this.clock.now() + timeoutMs
    return new Promise<T>((resolve, reject) => {
      // Отмена могла прийти до старта ожидания (signal уже aborted).
      if (this.settled) {
        reject(this.earlyCancel ?? new AssistantTimeout(this.deps.actionId, this.deps.dialogId))
        return
      }
      this.rejectWait = reject

      const cleanup = () => {
        this.clearTimer?.()
        this.clearTimer = null
        this.checkNow = null
        this.rejectWait = null
      }

      const finish = (error: Error | null, value: T | null) => {
        if (this.settled) return
        this.settled = true
        cleanup()
        if (error) {
          reject(error)
        } else if (value === null) {
          reject(new Error('Агент завершил действие, но результат в БЗ не оформлен'))
        } else {
          resolve(value)
        }
      }

      const check = async () => {
        if (this.settled || this.checking) return
        this.checking = true
        try {
          let finished = false
          try {
            finished = await this.deps.isFinished()
          } catch {
            // Временная ошибка соединения — повторим на следующем тике.
          }
          if (finished) {
            finish(null, await this.deps.readResult())
            return
          }
        } catch (error) {
          finish(error instanceof Error ? error : new Error(String(error)), null)
          return
        } finally {
          this.checking = false
        }
        if (this.settled) return
        const remaining = deadline - this.clock.now()
        if (remaining <= 0) {
          finish(new AssistantTimeout(this.deps.actionId, this.deps.dialogId), null)
          return
        }
        this.clearTimer?.()
        this.clearTimer = this.clock.setTimer(
          Math.min(this.pollIntervalMs, remaining),
          () => void check(),
        )
      }

      this.checkNow = () => void check()
      void check()
    })
  }

  /** sc-событие socket: проверить завершение не дожидаясь следующего тика. */
  poke(): void {
    this.checkNow?.()
  }

  /** Мягкая отмена: перестаём ждать, не меняя конструкции в БЗ. */
  wake(): void {
    if (this.settled) return
    this.settled = true
    const cancel = new AssistantCancelled(this.deps.actionId)
    this.earlyCancel = cancel
    const reject = this.rejectWait
    this.clearTimer?.()
    this.clearTimer = null
    this.checkNow = null
    this.rejectWait = null
    reject?.(cancel)
  }

  /** Читает готовый результат; повторной отправки вопроса не требуется. */
  async readActionResult(): Promise<T | null> {
    if (!(await this.deps.isFinished())) return null
    return this.deps.readResult()
  }
}
