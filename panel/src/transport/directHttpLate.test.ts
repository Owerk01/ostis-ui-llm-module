import assert from 'node:assert/strict'
import test from 'node:test'

import { DirectHttpTransport } from './directHttp.ts'
import { AssistantBusy, AssistantCancelled, AssistantTimeout } from './errors.ts'
import type { AssistantMessage } from './types.ts'

const DIALOG_ID = 'dialog-abc123'
const MESSAGE_ID = 'msg-42'

const answer: AssistantMessage = {
  id: MESSAGE_ID,
  role: 'assistant',
  text: 'готовый ответ',
  state: 'done',
  createdAt: '2026-11-25T00:00:00Z',
  code: 'ok',
  retryable: false,
}

const user: AssistantMessage = {
  id: 'msg-41',
  role: 'user',
  text: 'вопрос',
  state: 'done',
  createdAt: '2026-11-25T00:00:00Z',
  code: 'ok',
  retryable: false,
}

interface SseEvent {
  event: string
  data: unknown
}

const meta: SseEvent = {
  event: 'meta',
  data: { message_id: MESSAGE_ID, dialog_id: DIALOG_ID, state: 'pending', code: 'pending' },
}

function sseResponse(events: SseEvent[], signal?: AbortSignal): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const item of events) {
        controller.enqueue(
          encoder.encode(`event: ${item.event}\ndata: ${JSON.stringify(item.data)}\n\n`),
        )
      }
      if (signal) {
        signal.addEventListener(
          'abort',
          () => controller.error(new DOMException('Aborted', 'AbortError')),
          { once: true },
        )
      }
    },
  })
  return new Response(body, { status: 200 })
}

function historyResponse(history: AssistantMessage[]): Response {
  return new Response(JSON.stringify(history), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })
}

function fakeFetch(
  ask: () => Response,
  history: AssistantMessage[],
  calls: string[],
): typeof fetch {
  return (async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    calls.push(url)
    if (url.endsWith('/ask')) return ask(init?.signal)
    if (url.includes('/history/')) return historyResponse(history)
    return new Response('not found', { status: 404 })
  }) as typeof fetch
}

test('test_late_result_recoverable: timeout с actionId, затем дочитка без нового вопроса', async () => {
  const calls: string[] = []
  const transport = new DirectHttpTransport(
    'http://assistant.test',
    fakeFetch((signal) => sseResponse([meta], signal), [user, answer], calls),
    50,
  )

  await assert.rejects(
    transport.ask(DIALOG_ID, 'вопрос'),
    (error: unknown) => {
      assert.ok(error instanceof AssistantTimeout)
      assert.equal(error.actionId, MESSAGE_ID)
      assert.equal(error.dialogId, DIALOG_ID)
      return true
    },
  )

  const recovered = await transport.readActionResult(MESSAGE_ID)
  assert.ok(recovered)
  assert.equal(recovered.id, MESSAGE_ID)
  assert.equal(recovered.text, answer.text)
  assert.equal(recovered.state, 'done')
  assert.equal(recovered.code, 'ok')
  assert.equal(calls.filter((url) => url.endsWith('/ask')).length, 1)
  assert.equal(calls.filter((url) => url.includes('/history/')).length, 1)
})

test('мягкая отмена: один вызов ask и ровно один ход в истории', async () => {
  const calls: string[] = []
  const cancelled: AssistantMessage = { ...answer, state: 'cancelled', code: 'cancelled' }
  const transport = new DirectHttpTransport(
    'http://assistant.test',
    fakeFetch(
      (signal) => sseResponse([meta, { event: 'cancelled', data: { message_id: MESSAGE_ID } }], signal),
      [user, cancelled],
      calls,
    ),
    1_000,
  )

  await assert.rejects(transport.ask(DIALOG_ID, 'вопрос'), AssistantCancelled)

  const history = await transport.history(DIALOG_ID)
  assert.equal(history.filter((message) => message.role === 'user').length, 1)
  assert.equal(history.filter((message) => message.role === 'assistant').length, 1)
  assert.equal(calls.filter((url) => url.endsWith('/ask')).length, 1)
})

test('переполнение очереди даёт AssistantBusy, а не строковый Error', async () => {
  const transport = new DirectHttpTransport(
    'http://assistant.test',
    (async () => new Response('busy', { status: 503 })) as typeof fetch,
  )
  await assert.rejects(transport.ask(DIALOG_ID, 'вопрос'), AssistantBusy)
})
