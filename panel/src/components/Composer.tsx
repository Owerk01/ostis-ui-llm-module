import { useState, type KeyboardEvent } from 'react'
import styles from './Composer.module.css'

interface ComposerProps {
  disabled: boolean
  onSend: (question: string) => void
}

export function Composer({ disabled, onSend }: ComposerProps) {
  const [value, setValue] = useState('')
  const canSend = !disabled && value.trim().length > 0

  const submit = () => {
    if (!canSend) return
    onSend(value.trim())
    setValue('')
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <div className={styles['oaa-composer']}>
      <label className={styles['oaa-label']} htmlFor="oaa-question">
        Вопрос
      </label>
      <div className={styles['oaa-row']}>
        <textarea
          id="oaa-question"
          className={styles['oaa-input']}
          value={value}
          rows={2}
          placeholder="Например: какие свойства есть у concept_ui_button?"
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
          disabled={disabled}
        />
        <button
          type="button"
          className={styles['oaa-send']}
          onClick={submit}
          disabled={!canSend}
        >
          Отправить
        </button>
      </div>
      <p className={styles['oaa-hint']}>
        Enter — отправить, Shift+Enter — перенос строки. Ассистент не изменяет интерфейс.
      </p>
    </div>
  )
}
