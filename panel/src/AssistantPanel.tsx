import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Composer } from './components/Composer'
import { errorHint } from './transport/errorHint'
import { isRetryable, outcomeCodeFromError, PENDING_CODE } from './transport/outcome.ts'
import { MessageList } from './components/MessageList'
import { StatusBar, type RequestState } from './components/StatusBar'
import { cx } from './components/cx'
import styles from './AssistantPanel.module.css'
import type {
  AssistantHealth,
  AssistantMessage,
  AssistantTransport,
  SourceRef,
} from './transport/types'

export interface AssistantPanelProps {
  transport: AssistantTransport
  dialogId?: string
  title?: string // по умолчанию «Ассистент разработчика ПИ»
  className?: string
  onSourceClick?: (ref: SourceRef) => void // редактор подсветит узел
  // --- ЗАРЕЗЕРВИРОВАНО, не реализовано ---
  // contextSelection?: ContextSelection
  // onContextChange?: (c: ContextSelection) => void
  // onProposedChange?: (p: ProposedChange) => void
}

const DEFAULT_TITLE = 'Ассистент разработчика ПИ'

function localId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function describeError(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'Не удалось получить ответ'
}

export function AssistantPanel({
  transport,
  dialogId: dialogIdProp,
  title = DEFAULT_TITLE,
  className,
  onSourceClick,
}: AssistantPanelProps) {
  const [messages, setMessages] = useState<AssistantMessage[]>([])
  const [dialogId, setDialogId] = useState<string | null>(dialogIdProp ?? null)
  const [health, setHealth] = useState<AssistantHealth | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [initError, setInitError] = useState<string | null>(null)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [now, setNow] = useState(() => performance.now())

  const activeRequest = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const refreshHealth = useCallback(async () => {
    try {
      const result = await transport.health()
      setHealth(result)
      setHealthError(null)
    } catch (error) {
      setHealth(null)
      setHealthError(describeError(error))
    }
  }, [transport])

  useEffect(() => {
    let alive = true

    void refreshHealth()

    void (async () => {
      try {
        const nextDialog = await transport.ensureDialog(dialogIdProp)
        if (!alive) return
        setDialogId(nextDialog)
        const history = await transport.history(nextDialog)
        if (!alive) return
        setMessages(history)
        setInitError(null)
      } catch (error) {
        if (alive) setInitError(describeError(error))
      }
    })()

    return () => {
      alive = false
      abortRef.current?.abort()
      abortRef.current = null
      activeRequest.current = null
    }
  }, [transport, dialogIdProp, refreshHealth])

  useEffect(() => {
    if (pendingId === null) return
    const timer = globalThis.setInterval(() => setNow(performance.now()), 100)
    return () => globalThis.clearInterval(timer)
  }, [pendingId])

  const run = useCallback(
    async (question: string, appendUser: boolean) => {
      const text = question.trim()
      if (!text || !dialogId || activeRequest.current) return

      const createdAt = new Date().toISOString()
      const pendingLocalId = localId('msg-local')
      const pendingMessage: AssistantMessage = {
        id: pendingLocalId,
        role: 'assistant',
        text: '',
        state: 'pending',
        createdAt,
        code: PENDING_CODE,
        retryable: false,
      }

      setMessages((previous) => {
        const next = appendUser
          ? [
              ...previous,
              {
                id: localId('msg-user'),
                role: 'user' as const,
                text,
                state: 'done' as const,
                code: 'ok' as const,
                retryable: false,
                createdAt,
              },
            ]
          : previous
        return [...next, pendingMessage]
      })
      activeRequest.current = pendingLocalId
      const started = performance.now()
      setPendingId(pendingLocalId)
      setStartedAt(started)
      setNow(started)

      try {
        const answer = await transport.ask(
          dialogId,
          text,
          (chunk) => {
            setMessages((previous) =>
              previous.map((message) =>
                message.id === pendingLocalId
                  ? { ...message, text: message.text + chunk, state: 'streaming' }
                  : message,
              ),
            )
          },
        )

        setMessages((previous) =>
          previous.map((message) => {
            if (message.id !== pendingLocalId) return message
            if (answer.state === 'cancelled') {
              return {
                ...message,
                ...answer,
                state: 'cancelled' as const,
                code: 'cancelled' as const,
                retryable: false,
                text: message.text || answer.text,
              }
            }
            return {
              ...answer,
              createdAt: message.createdAt,
              text: answer.text || message.text,
            }
          }),
        )
      } catch (error) {
        const errorText = describeError(error)
        const code = outcomeCodeFromError(error)
        setMessages((previous) =>
          previous.map((message) =>
            message.id === pendingLocalId
              ? {
                  ...message,
                  state: 'error' as const,
                  code,
                  retryable: isRetryable(code),
                  error: errorText,
                  text: message.text,
                }
              : message,
          ),
        )
        void refreshHealth()
      } finally {
        if (activeRequest.current === pendingLocalId) {
          activeRequest.current = null
          setPendingId(null)
          setStartedAt(null)
        }
      }
    },
    [dialogId, refreshHealth, transport],
  )

  const send = useCallback((question: string) => void run(question, true), [run])

  const cancel = useCallback(() => {
    const current = pendingId
    if (!current) return
    activeRequest.current = null
    setPendingId(null)
    setStartedAt(null)
    setMessages((previous) =>
      previous.map((message) =>
        message.id === current
          ? {
              ...message,
              state: 'cancelled' as const,
              code: 'cancelled' as const,
              retryable: false,
            }
          : message,
      ),
    )
    void transport.cancel(current)
  }, [pendingId, transport])

  const retry = useCallback(
    (messageId: string) => {
      const index = messages.findIndex((message) => message.id === messageId)
      if (index < 0) return
      let question = ''
      for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
        if (messages[cursor].role === 'user') {
          question = messages[cursor].text
          break
        }
      }
      if (!question) return
      // Повтор — новый полный ход: пользовательское сообщение добавляется и
      // локально, и в БЗ; прежний неуспешный ход остаётся в истории.
      void run(question, true)
    },
    [messages, run],
  )

  const requestState: RequestState = pendingId
    ? 'pending'
    : messages.some((message) => message.state === 'error')
      ? 'error'
      : 'idle'
  const elapsedMs = startedAt === null ? 0 : Math.max(0, now - startedAt)
  const fallback = health?.kb.knowledgeSource === 'fallback'
  // Правило гейта относится к sc-режиму редактора; в direct-http
  // узла состояния нет, поэтому гейт не применяется.
  const scMode = transport.kind === 'sc-memory'
  const schemaLoaded = !scMode || (health?.schemaLoaded ?? true)
  const agentAlive = !scMode || (health?.agentAlive ?? true)
  const chatVisible = schemaLoaded
  const inputBlocked = !schemaLoaded || !agentAlive

  const statusProps = useMemo(
    () => ({ health, healthError, state: requestState, elapsedMs, onCancel: cancel }),
    [health, healthError, requestState, elapsedMs, cancel],
  )

  return (
    <section className={cx(styles['oaa-panel'], className)} aria-label={title}>
      <header className={styles['oaa-header']}>
        <div className={styles['oaa-heading']}>
          <h2 className={styles['oaa-title']}>{title}</h2>
          <p className={styles['oaa-subtitle']}>
            Вопросы о типологии компонентов, свойствах, принципах и методике разработки ПИ
          </p>
        </div>
        <span className={styles['oaa-badge']}>OSTIS</span>
      </header>

      <StatusBar {...statusProps} />

      {scMode && health && health.schemaLoaded === false ? (
        <div className={styles['oaa-banner']} role="status">
          Схема ассистента не загружена в БЗ — чат скрыт. Выполните make kb-load.
        </div>
      ) : null}

      {scMode && health && schemaLoaded && health.agentAlive === false ? (
        <div className={cx(styles['oaa-banner'], styles['oaa-banner-error'])} role="alert">
          Агент диалога не запущен. Ввод заблокирован. Запустите агент: make agent-start.
        </div>
      ) : null}

      {fallback ? (
        <div className={styles['oaa-banner']} role="status">
          Знания загружены из локальной копии, БЗ недоступна. Ответы ограничены knowledge
          pack {health?.kb.packVersion}.
        </div>
      ) : null}

      {initError || healthError ? (
        <div className={cx(styles['oaa-banner'], styles['oaa-banner-error'])} role="alert">
          {initError ?? healthError}. {errorHint(transport.kind)}.
        </div>
      ) : null}

      {chatVisible ? (
        <MessageList
          messages={messages}
          onSourceClick={onSourceClick}
          onRetry={retry}
          onSuggestion={send}
        />
      ) : null}

      {chatVisible ? (
        <Composer
          disabled={!dialogId || pendingId !== null || inputBlocked}
          onSend={send}
        />
      ) : null}
    </section>
  )
}
