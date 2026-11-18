import type { AssistantHealth } from '../transport/types'
import { formatElapsed } from '../utils/formatElapsed'
import styles from './StatusBar.module.css'

export type RequestState = 'idle' | 'pending' | 'error'

interface StatusBarProps {
  health: AssistantHealth | null
  healthError: string | null
  state: RequestState
  elapsedMs: number
  onCancel?: () => void
}

export function StatusBar({
  health,
  healthError,
  state,
  elapsedMs,
  onCancel,
}: StatusBarProps) {
  const reachable = health?.llm.reachable ?? false
  const source = health?.kb.knowledgeSource ?? 'fallback'
  const scMode = health?.llm.backend === 'sc-memory'

  return (
    <div className={styles['oaa-status']} role="status">
      <span
        className={`${styles['oaa-dot']} ${reachable ? styles['oaa-dot-ok'] : styles['oaa-dot-bad']}`}
        aria-hidden="true"
      />
      <span className={styles['oaa-item']}>
        {health ? (
          scMode ? (
            <>
              LLM: <span className={styles['oaa-strong']}>через sc-агент</span>
              {!reachable ? ' — БЗ недоступна' : ''}
            </>
          ) : (
            <>
              LLM: <span className={styles['oaa-strong']}>{health.llm.model}</span>
              {!reachable ? ' — недоступна' : ''}
            </>
          )
        ) : healthError ? (
          'Сервис недоступен'
        ) : (
          'Проверка сервиса…'
        )}
      </span>

      <span className={styles['oaa-sep']} aria-hidden="true">
        ·
      </span>
      <span className={styles['oaa-item']}>
        {source === 'kb' ? 'Знания из БЗ' : 'Знания из локальной копии'}
      </span>

      {health && health.kb.packVersion ? (
        <>
          <span className={styles['oaa-sep']} aria-hidden="true">
            ·
          </span>
          <span className={`${styles['oaa-item']} ${styles['oaa-mono']}`}>
            pack {health.kb.packVersion}
          </span>
        </>
      ) : null}

      {state === 'pending' ? (
        <span className={styles['oaa-pending']}>
          <span className={styles['oaa-timer']} aria-label="Время обработки запроса">
            {formatElapsed(elapsedMs)}
          </span>
          <button type="button" className={styles['oaa-cancel']} onClick={onCancel}>
            Отмена
          </button>
        </span>
      ) : null}
    </div>
  )
}
