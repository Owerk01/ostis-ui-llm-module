import styles from './SourceChips.module.css'

import type { SourceRef } from '../transport/types'

interface SourceChipsProps {
  sources: SourceRef[]
  onSourceClick?: (ref: SourceRef) => void
}

export function SourceChips({ sources, onSourceClick }: SourceChipsProps) {
  if (sources.length === 0) return null

  return (
    <div className={styles['oaa-chips']} aria-label="Основания ответа">
      {sources.map((source) => (
        <button
          key={source.idtf}
          type="button"
          className={styles['oaa-chip']}
          title={
            source.labelRu
              ? `${source.labelRu}: ${source.idtf}`
              : `Узел базы знаний ${source.idtf}`
          }
          onClick={() => onSourceClick?.(source)}
          disabled={!onSourceClick}
        >
          <span className={styles['oaa-chip-idtf']}>{source.idtf}</span>
          {source.labelRu ? (
            <span className={styles['oaa-chip-label']}>{source.labelRu}</span>
          ) : null}
        </button>
      ))}
    </div>
  )
}
