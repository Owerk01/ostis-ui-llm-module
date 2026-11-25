import assert from 'node:assert/strict'
import test from 'node:test'

import { AssistantCancelled, AssistantTimeout } from './errors.ts'
import { LateResult, type Clock } from './lateResult.ts'

class FakeClock implements Clock {
  time = 0
  private timers: Array<{ at: number; fn: () => void; active: boolean }> = []

  now(): number {
    return this.time
  }

  setTimer(delayMs: number, fn: () => void): () => void {
    const timer = { at: this.time + delayMs, fn, active: true }
    this.timers.push(timer)
    return () => {
      timer.active = false
    }
  }

  async advance(ms: number): Promise<void> {
    const target = this.time + ms
    for (;;) {
      const next = this.timers
        .filter((timer) => timer.active && timer.at <= target)
        .sort((a, b) => a.at - b.at)[0]
      if (!next) break
      next.active = false
      this.time = Math.max(this.time, next.at)
      next.fn()
      // Дать асинхронной проверке (await isFinished) завершиться.
      await new Promise<void>((resolve) => setTimeout(resolve, 0))
    }
    this.time = target
  }
}

const answer = {
  id: 'msg-1',
  role: 'assistant' as const,
  text: 'готовый ответ',
  state: 'done' as const,
  createdAt: '2026-11-25T00:00:00Z',
  code: 'ok' as const,
  retryable: false,
}

test('test_late_result_recoverable: таймаут 1 с, ответ через 3 с, один ход', async () => {
  const clock = new FakeClock()
  let ready = false
  let finishedChecks = 0
  let reads = 0
  const waiter = new LateResult({
    actionId: '70207',
    dialogId: 'dialog-1',
    isFinished: async () => {
      finishedChecks += 1
      return ready
    },
    readResult: async () => {
      reads += 1
      return answer
    },
    clock,
    pollIntervalMs: 100,
  })

  const waiting = waiter.wait(1_000)
  const timedOut = assert.rejects(waiting, (error: unknown) => {
    assert.ok(error instanceof AssistantTimeout)
    assert.equal(error.actionId, '70207')
    assert.equal(error.dialogId, 'dialog-1')
    return true
  })
  await clock.advance(1_000)
  await timedOut

  ready = true // агент дописал ответ через 3 с
  assert.deepEqual(await waiter.readActionResult(), answer)
  assert.equal(reads, 1)
  assert.ok(finishedChecks > 1)
})

test('мягкая отмена не создаёт второй ход и не трогает результат в БЗ', async () => {
  const clock = new FakeClock()
  let ready = false
  let reads = 0
  const waiter = new LateResult({
    actionId: '70208',
    isFinished: async () => ready,
    readResult: async () => {
      reads += 1
      return answer
    },
    clock,
  })

  const waiting = waiter.wait(5_000)
  const cancelled = assert.rejects(waiting, (error: unknown) => {
    assert.ok(error instanceof AssistantCancelled)
    assert.equal(error.actionId, '70208')
    return true
  })
  await clock.advance(1)
  waiter.wake()
  await cancelled

  ready = true
  assert.deepEqual(await waiter.readActionResult(), answer)
  assert.equal(reads, 1)
})

test('отмена до старта ожидания не оставляет вечный promise', async () => {
  const waiter = new LateResult({
    actionId: '70209',
    isFinished: async () => false,
    readResult: async () => answer,
    clock: new FakeClock(),
  })
  waiter.wake()
  await assert.rejects(waiter.wait(1_000), AssistantCancelled)
})

test('временный сбой чтения статуса не прерывает ожидание', async () => {
  const clock = new FakeClock()
  let attempts = 0
  const waiter = new LateResult({
    actionId: '70210',
    isFinished: async () => {
      attempts += 1
      if (attempts < 3) throw new Error('connection reset')
      return true
    },
    readResult: async () => answer,
    clock,
    pollIntervalMs: 100,
  })

  const waiting = waiter.wait(1_000)
  await new Promise<void>((resolve) => setTimeout(resolve, 0))
  await clock.advance(300)
  assert.deepEqual(await waiting, answer)
  assert.equal(attempts, 3)
})
