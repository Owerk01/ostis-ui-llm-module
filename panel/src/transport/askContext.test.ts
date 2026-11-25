import assert from 'node:assert/strict'
import test from 'node:test'

import { contextPayload, normalizeAskOptions } from './askOptions.ts'
import { DirectHttpTransport } from './directHttp.ts'
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

test('normalizeAskOptions: плоский onDelta/signal сохраняются', () => {
  const onDelta = (_chunk: string) => {}
  const signal = new AbortController().signal
  assert.deepEqual(normalizeAskOptions(onDelta, signal), { onDelta, signal })
  assert.deepEqual(normalizeAskOptions(undefined, signal), { signal })
})

test('normalizeAskOptions: options.context и signal из 4-го аргумента', () => {
  const signal = new AbortController().signal
  const normalized = normalizeAskOptions(
    {
      context: { mode: 'selection', interfaceId: 'ex_login', componentIds: ['ex_login_cmp_10'] },
    },
    signal,
  )
  assert.equal(normalized.context?.mode, 'selection')
  assert.equal(normalized.signal, signal)
})

test('contextPayload: none не отправляется, selection/whole — snake_case', () => {
  assert.equal(contextPayload(normalizeAskOptions()), undefined)
  assert.equal(contextPayload(normalizeAskOptions({ context: { mode: 'none' } })), undefined)
  assert.deepEqual(
    contextPayload(
      normalizeAskOptions({
        context: {
          mode: 'selection',
          interfaceId: 'ex_login',
          componentIds: ['ex_login_cmp_10'],
        },
      }),
    ),
    { mode: 'selection', interface_id: 'ex_login', component_ids: ['ex_login_cmp_10'] },
  )
  assert.deepEqual(
    contextPayload(normalizeAskOptions({ context: { mode: 'whole', interfaceId: 'ex_login' } })),
    { mode: 'whole', interface_id: 'ex_login' },
  )
})

test('direct-http: контекст уходит в /ask, legacy onDelta работает', async () => {
  let body: Record<string, unknown> = {}
  const chunks: string[] = []
  const encoder = new TextEncoder()
  const fetchImpl = (async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input)
    if (!url.endsWith('/ask')) return new Response('not found', { status: 404 })
    body = JSON.parse(String(init?.body)) as Record<string, unknown>
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(
          encoder.encode(
            `event: meta\ndata: ${JSON.stringify({ message_id: MESSAGE_ID, dialog_id: DIALOG_ID })}\n\n`,
          ),
        )
        controller.enqueue(encoder.encode(`event: delta\ndata: ${JSON.stringify({ text: 'часть' })}\n\n`))
        controller.enqueue(
          encoder.encode(`event: done\ndata: ${JSON.stringify({ message: answer })}\n\n`),
        )
        controller.close()
      },
    })
    return new Response(stream, { status: 200 })
  }) as typeof fetch

  const transport = new DirectHttpTransport('http://assistant.test', fetchImpl, 1_000)
  const result = await transport.ask(DIALOG_ID, 'что делает кнопка?', {
    context: { mode: 'selection', interfaceId: 'ex_login', componentIds: ['ex_login_cmp_10'] },
    onDelta: (chunk) => chunks.push(chunk),
  })

  assert.deepEqual(body.context, {
    mode: 'selection',
    interface_id: 'ex_login',
    component_ids: ['ex_login_cmp_10'],
  })
  assert.deepEqual(chunks, ['часть'])
  assert.equal(result.text, answer.text)
})
