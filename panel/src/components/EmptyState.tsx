import styles from './EmptyState.module.css'

interface EmptyStateProps {
  onSuggestion: (question: string) => void
}

const SUGGESTIONS = [
  'Какие типы компонентов есть в базе знаний среды?',
  'Что задаёт свойство action_id?',
  'Чем concept_ui_button отличается от concept_ui_menu_item?',
  'Что означает принцип семантической совместимости?',
]

export function EmptyState({ onSuggestion }: EmptyStateProps) {
  return (
    <div className={styles['oaa-empty']}>
      <p className={styles['oaa-empty-title']}>Спросите о предметной области разработки ПИ</p>
      <p className={styles['oaa-empty-text']}>
        Типология компонентов, свойства, принципы, методика и устройство среды. Ответы
        опираются только на базу знаний среды.
      </p>
      <div className={styles['oaa-suggestions']}>
        {SUGGESTIONS.map((question) => (
          <button
            key={question}
            type="button"
            className={styles['oaa-suggestion']}
            onClick={() => onSuggestion(question)}
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  )
}
