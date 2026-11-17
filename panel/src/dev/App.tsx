import { useMemo, useState } from 'react'

import { AssistantPanel } from '../AssistantPanel'
import { DEFAULT_BASE_URL, DirectHttpTransport } from '../transport/directHttp'
import type { SourceRef } from '../transport/types'
import styles from './App.module.css'

const STORAGE_KEY = 'oaa.dev.baseUrl'

type TransportKind = 'direct-http' | 'sc-memory'

export function App() {
  const [baseUrl, setBaseUrl] = useState(
    () => window.localStorage.getItem(STORAGE_KEY) ?? DEFAULT_BASE_URL,
  )
  const [appliedBaseUrl, setAppliedBaseUrl] = useState(baseUrl)
  const [kind, setKind] = useState<TransportKind>('direct-http')
  const [lastSource, setLastSource] = useState<SourceRef | null>(null)

  // Транспорт должен быть стабильным: создаём его только при смене адреса.
  const transport = useMemo(() => new DirectHttpTransport(appliedBaseUrl), [appliedBaseUrl])

  const apply = () => {
    const next = baseUrl.trim().replace(/\/+$/, '')
    window.localStorage.setItem(STORAGE_KEY, next)
    setAppliedBaseUrl(next || DEFAULT_BASE_URL)
  }

  return (
    <div className={styles['oaa-dev']}>
      <aside className={styles['oaa-dev-sidebar']}>
        <h1 className={styles['oaa-dev-title']}>Dev-стенд панели</h1>
        <p className={styles['oaa-dev-text']}>
          Отдельное приложение для M1. В редактор панель встраивается одним компонентом{' '}
          <code className={styles['oaa-code']}>{'<AssistantPanel transport={…} />'}</code>.
        </p>

        <label className={styles['oaa-dev-label']} htmlFor="oaa-dev-kind">
          Транспорт
        </label>
        <select
          id="oaa-dev-kind"
          className={styles['oaa-dev-input']}
          value={kind}
          onChange={(event) => setKind(event.target.value as TransportKind)}
        >
          <option value="direct-http">direct-http (отладочный, M1)</option>
          <option value="sc-memory">sc-memory (M2-T9, пока недоступен)</option>
        </select>

        <label className={styles['oaa-dev-label']} htmlFor="oaa-dev-url">
          Адрес сервиса
        </label>
        <input
          id="oaa-dev-url"
          className={styles['oaa-dev-input']}
          value={baseUrl}
          onChange={(event) => setBaseUrl(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') apply()
          }}
          spellCheck={false}
        />
        <button type="button" className={styles['oaa-dev-button']} onClick={apply}>
          Применить
        </button>

        <p className={styles['oaa-dev-hint']}>
          sc-сервер для режима sc-memory: <code className={styles['oaa-code']}>ws://127.0.0.1:8090/ws_json</code>
        </p>

        {kind === 'sc-memory' ? (
          <p className={styles['oaa-dev-warning']}>
            Транспорт sc-memory появится в M2-T9. Сейчас панель работает через direct-http;
            смысловые конструкции диалога в БЗ ещё не пишутся.
          </p>
        ) : null}

        {lastSource ? (
          <div className={styles['oaa-dev-source']}>
            <span className={styles['oaa-dev-label']}>Выбрано основание</span>
            <code className={styles['oaa-code']}>{lastSource.idtf}</code>
            {lastSource.labelRu ? <span>{lastSource.labelRu}</span> : null}
          </div>
        ) : null}
      </aside>

      <main className={styles['oaa-dev-main']}>
        <AssistantPanel
          transport={transport}
          className={styles['oaa-dev-panel']}
          onSourceClick={setLastSource}
        />
      </main>
    </div>
  )
}
