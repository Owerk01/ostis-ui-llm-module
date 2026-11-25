/**
 * Отладочный HTTP-транспорт.
 *
 * Работает с FastAPI-сервисом direct-http: /health, /dialog, /history/{id},
 * /ask (SSE), /cancel. В основном режиме панель использует scMemory.ts.
 */

import type {
  AssistantHealth,
  AssistantMessage,
  AssistantTransport,
  MessageState,
  SourceRef,
} from './types'
import { DialogNotFoundError } from './types'

export const DEFAULT_BASE_URL = 'http://127.0.0.1:8770'

interface SseEvent {
  event: string
  data: string
}

interface ServerMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  state: string
  createdAt: string
  sources?: SourceRef[]
  error?: string | null
  scAddr?: number
}

const MESSAGE_STATES: ReadonlySet<string> = new Set([
  'pending',
  'streaming',
  'done',
  'error',
  'cancelled',
])

function toState(value: string): MessageState {
  return MESSAGE_STATES.has(value) ? (value as MessageState) : 'done'
}

function toMessage(raw: ServerMessage): AssistantMessage {
  return {
    id: raw.id,
    role: raw.role,
    text: raw.text,
    state: toState(raw.state),
    createdAt: raw.createdAt,
    sources: raw.sources,
    error: raw.error ?? undefined,
    scAddr: raw.scAddr,
  }
}

async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)

        let event = 'message'
        const data: string[] = []
        for (const line of block.split('\n')) {
          const clean = line.endsWith('\r') ? line.slice(0, -1) : line
          if (clean.startsWith('event:')) event = clean.slice(6).trim()
          else if (clean.startsWith('data:')) data.push(clean.slice(5).trimStart())
        }
        if (data.length > 0) yield { event, data: data.join('\n') }
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export class DirectHttpTransport implements AssistantTransport {
  readonly kind = 'direct-http' as const

  private readonly baseUrl: string
  private readonly fetchImpl: typeof fetch
  private active: { controller: AbortController; messageId?: string } | null = null

  constructor(baseUrl: string = DEFAULT_BASE_URL, fetchImpl: typeof fetch = fetch) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    // fetch нельзя вызывать как метод объекта: в браузере это даёт Illegal invocation.
    this.fetchImpl = fetchImpl.bind(globalThis)
  }

  async health(): Promise<AssistantHealth> {
    const response = await this.fetchImpl(`${this.baseUrl}/health`)
    if (!response.ok) throw new Error(`Сервис ответил ${response.status}`)
    const body = (await response.json()) as AssistantHealth
    const timeouts = body.timeouts
      ? {
          llmTimeoutS: body.timeouts.llmTimeoutS ?? body.timeouts.dialogClientTimeoutS ?? 25,
          dialogClientTimeoutS:
            body.timeouts.dialogClientTimeoutS ?? body.timeouts.llmTimeoutS ?? 35,
        }
      : undefined
    return {
      llm: {
        backend: body.llm?.backend ?? 'unknown',
        model: body.llm?.model ?? 'unknown',
        reachable: Boolean(body.llm?.reachable),
      },
      kb: {
        connected: Boolean(body.kb?.connected),
        knowledgeSource: body.kb?.knowledgeSource === 'kb' ? 'kb' : 'fallback',
        packVersion: body.kb?.packVersion ?? 'unknown',
      },
      schemaLoaded: body.schemaLoaded,
      agentAlive: body.agentAlive,
      state: body.state,
      model: body.model ?? body.llm.model,
      packVersion: body.packVersion ?? body.kb.packVersion,
      promptVersion: body.promptVersion,
      knowledgeSource: body.knowledgeSource ?? body.kb.knowledgeSource,
      queueDepth: body.queueDepth,
      contractVersion: body.contractVersion,
      timeouts,
    }
  }

  async ensureDialog(dialogId?: string): Promise<string> {
    if (dialogId) {
      const response = await this.fetchImpl(
        `${this.baseUrl}/dialog/${encodeURIComponent(dialogId)}`,
      )
      if (response.status === 404) throw new DialogNotFoundError(dialogId)
      if (!response.ok) throw new Error(`Не удалось проверить диалог: ${response.status}`)
      const body = (await response.json()) as { exists?: boolean }
      if (body.exists === false) throw new DialogNotFoundError(dialogId)
      return dialogId
    }
    const response = await this.fetchImpl(`${this.baseUrl}/dialog`, { method: 'POST' })
    if (!response.ok) throw new Error(`Не удалось создать диалог: ${response.status}`)
    const body = (await response.json()) as { dialog_id: string }
    if (!body.dialog_id) throw new Error('Сервис не вернул идентификатор диалога')
    return body.dialog_id
  }

  async history(dialogId: string): Promise<AssistantMessage[]> {
    const response = await this.fetchImpl(
      `${this.baseUrl}/history/${encodeURIComponent(dialogId)}`,
    )
    if (!response.ok) throw new Error(`Не удалось прочитать историю: ${response.status}`)
    const body = (await response.json()) as ServerMessage[]
    return body.map(toMessage)
  }

  async ask(
    dialogId: string,
    question: string,
    onDelta?: (chunk: string) => void,
    signal?: AbortSignal,
  ): Promise<AssistantMessage> {
    if (this.active) {
      // Один активный запрос на транспорт: панель блокирует повторную отправку.
      throw new Error('Предыдущий запрос ещё выполняется')
    }

    const controller = new AbortController()
    const active: { controller: AbortController; messageId?: string } = { controller }
    this.active = active

    const onExternalAbort = () => controller.abort()
    if (signal) {
      if (signal.aborted) controller.abort()
      else signal.addEventListener('abort', onExternalAbort, { once: true })
    }

    try {
      const response = await this.fetchImpl(`${this.baseUrl}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, dialog_id: dialogId }),
        signal: controller.signal,
      })

      if (!response.ok) {
        if (response.status === 404) throw new DialogNotFoundError(dialogId)
        const detail = await this.readError(response)
        throw new Error(detail)
      }
      if (!response.body) throw new Error('Сервис не вернул поток ответа')

      let finalMessage: AssistantMessage | null = null

      for await (const sse of readSse(response.body)) {
        const payload = this.parseData(sse)
        if (!payload) continue

        if (sse.event === 'meta') {
          if (typeof payload.message_id === 'string') active.messageId = payload.message_id
        } else if (sse.event === 'delta') {
          const text = typeof payload.text === 'string' ? payload.text : ''
          if (text) onDelta?.(text)
        } else if (sse.event === 'done') {
          if (payload.message) finalMessage = toMessage(payload.message as ServerMessage)
        } else if (sse.event === 'cancelled') {
          const message = payload.message as ServerMessage | undefined
          finalMessage = message
            ? { ...toMessage(message), state: 'cancelled' }
            : this.localMessage(active.messageId, 'cancelled')
        } else if (sse.event === 'error') {
          const error = typeof payload.error === 'string' ? payload.error : 'Ошибка сервиса'
          throw new Error(error)
        }
      }

      if (finalMessage) return finalMessage
      return this.localMessage(active.messageId, 'done')
    } catch (error) {
      if (this.isAbort(error)) {
        return this.localMessage(active.messageId, 'cancelled')
      }
      throw error instanceof Error ? error : new Error(String(error))
    } finally {
      signal?.removeEventListener('abort', onExternalAbort)
      if (this.active === active) this.active = null
    }
  }

  async cancel(_messageId: string): Promise<void> {
    const active = this.active
    if (!active) return
    // В direct-http отмена — это AbortController плюс мягкий маркер в сервисе.
    active.controller.abort()
    if (!active.messageId) return
    try {
      await this.fetchImpl(`${this.baseUrl}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: active.messageId }),
      })
    } catch {
      // Отмена не должна ломать UI: поток уже прерван локально.
    }
  }

  private parseData(event: SseEvent): Record<string, unknown> | null {
    try {
      const parsed = JSON.parse(event.data) as unknown
      return parsed !== null && typeof parsed === 'object'
        ? (parsed as Record<string, unknown>)
        : null
    } catch {
      return null
    }
  }

  private async readError(response: Response): Promise<string> {
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) return body.detail
    } catch {
      // тело не JSON — покажем статус
    }
    return `Сервис ответил ${response.status}`
  }

  private isAbort(error: unknown): boolean {
    return error instanceof DOMException
      ? error.name === 'AbortError'
      : error instanceof Error && error.name === 'AbortError'
  }

  private localMessage(
    serverId: string | undefined,
    state: MessageState,
  ): AssistantMessage {
    return {
      id: serverId ?? `local-${Date.now()}`,
      role: 'assistant',
      text: '',
      state,
      createdAt: new Date().toISOString(),
    }
  }
}
