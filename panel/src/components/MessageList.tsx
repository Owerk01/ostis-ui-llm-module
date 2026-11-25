import type { AssistantMessage, SourceRef } from '../transport/types'
import { EmptyState } from './EmptyState'
import { SourceChips } from './SourceChips'
import styles from './MessageList.module.css'

interface MessageListProps {
  messages: AssistantMessage[]
  onSourceClick?: (ref: SourceRef) => void
  onRetry: (messageId: string) => void
  onSuggestion: (question: string) => void
}

function formatTime(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function stateLabel(message: AssistantMessage): string {
  if (message.state === 'pending') return 'Обработка запроса…'
  if (message.state === 'streaming') return 'Формирование ответа…'
  return ''
}

export function MessageList({
  messages,
  onSourceClick,
  onRetry,
  onSuggestion,
}: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className={styles['oaa-list-wrap']}>
        <EmptyState onSuggestion={onSuggestion} />
      </div>
    )
  }

  return (
    <ul className={styles['oaa-list']} aria-live="polite" aria-label="Лента сообщений">
      {messages.map((message) => {
        const isPending = message.state === 'pending' || message.state === 'streaming'
        return (
          <li
            key={message.id}
            className={`${styles['oaa-row']} ${
              message.role === 'user' ? styles['oaa-row-user'] : styles['oaa-row-assistant']
            }`}
          >
            <div className={styles['oaa-meta']}>
              <span className={styles['oaa-author']}>
                {message.role === 'user' ? 'Вы' : 'Среда'}
              </span>
              <time className={styles['oaa-time']} dateTime={message.createdAt}>
                {formatTime(message.createdAt)}
              </time>
            </div>

            <div
              className={`${styles['oaa-bubble']} ${
                message.role === 'user'
                  ? styles['oaa-bubble-user']
                  : styles['oaa-bubble-assistant']
              }`}
            >
              {message.text ? (
                <span className={styles['oaa-text']}>{message.text}</span>
              ) : isPending ? (
                <span className={styles['oaa-text']}>Обработка запроса…</span>
              ) : null}

              {isPending ? (
                <span className={styles['oaa-working']}>
                  <span className={styles['oaa-spinner']} aria-hidden="true" />
                  <span className={styles['oaa-working-label']}>{stateLabel(message)}</span>
                </span>
              ) : null}

              {message.state === 'cancelled' ? (
                <span className={styles['oaa-cancelled']}>Отменено</span>
              ) : null}

              {message.state === 'error' ? (
                <span className={styles['oaa-error']} role="alert">
                  <span>{message.error ?? 'Не удалось получить ответ'}</span>
                  {message.retryable ? (
                    <button
                      type="button"
                      className={styles['oaa-retry']}
                      onClick={() => onRetry(message.id)}
                    >
                      Повторить
                    </button>
                  ) : null}
                </span>
              ) : null}
            </div>

            {message.role === 'assistant' && message.sources?.length ? (
              <SourceChips sources={message.sources} onSourceClick={onSourceClick} />
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}
