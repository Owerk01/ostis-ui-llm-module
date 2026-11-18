import { useMemo, useState } from 'react'
import { ScClient } from 'ts-sc-client'

import { AssistantPanel } from '../AssistantPanel'
import { DEFAULT_BASE_URL, DirectHttpTransport } from '../transport/directHttp'
import { DEFAULT_SC_URL, ScMemoryTransport } from '../transport/scMemory'
import type { SourceRef } from '../transport/types'
import styles from './App.module.css'

const STORAGE_BASE_URL = 'oaa.dev.baseUrl'
const STORAGE_SC_URL = 'oaa.dev.scUrl'
const STORAGE_KIND = 'oaa.dev.kind'

type TransportKind = 'direct-http' | 'sc-memory'

export function App() {
  const [baseUrl, setBaseUrl] = useState(
    () => window.localStorage.getItem(STORAGE_BASE_URL) ?? DEFAULT_BASE_URL,
  )
  const [scUrl, setScUrl] = useState(
    () => window.localStorage.getItem(STORAGE_SC_URL) ?? DEFAULT_SC_URL,
  )
  const [applied, setApplied] = useState(() => ({
    baseUrl,
    scUrl,
  }))
  const [kind, setKind] = useState<TransportKind>(() => {
    const stored = window.localStorage.getItem(STORAGE_KIND)
    return stored === 'direct-http' ? 'direct-http' : 'sc-memory'
  })
  const [lastSource, setLastSource] = useState<SourceRef | null>(null)

  // Транспорт должен быть стабильным: создаём его только при смене режима или адреса.
  const transport = useMemo(
    () =>
      kind === 'sc-memory'
        ? new ScMemoryTransport(new ScClient(applied.scUrl))
        : new DirectHttpTransport(applied.baseUrl),
    [kind, applied],
  )

  const apply = () => {
    const next = {
      baseUrl: baseUrl.trim().replace(/\/+$/, '') || DEFAULT_BASE_URL,
      scUrl: scUrl.trim() || DEFAULT_SC_URL,
    }
    window.localStorage.setItem(STORAGE_BASE_URL, next.baseUrl)
    window.localStorage.setItem(STORAGE_SC_URL, next.scUrl)
    setApplied(next)
  }

  const changeKind = (value: TransportKind) => {
    setKind(value)
    window.localStorage.setItem(STORAGE_KIND, value)
  }

  return (
    <div className={styles['oaa-dev']}>
      <aside className={styles['oaa-dev-sidebar']}>
        <h1 className={styles['oaa-dev-title']}>Dev-стенд панели</h1>
        <p className={styles['oaa-dev-text']}>
          Отдельное приложение. В редактор панель встраивается одним компонентом{' '}
          <code className={styles['oaa-code']}>{'<AssistantPanel transport={…} />'}</code>.
        </p>

        <label className={styles['oaa-dev-label']} htmlFor="oaa-dev-kind">
          Транспорт
        </label>
        <select
          id="oaa-dev-kind"
          className={styles['oaa-dev-input']}
          value={kind}
          onChange={(event) => changeKind(event.target.value as TransportKind)}
        >
          <option value="sc-memory">sc-memory (боевой, через БЗ)</option>
          <option value="direct-http">direct-http (отладочный)</option>
        </select>

        {kind === 'sc-memory' ? (
          <>
            <label className={styles['oaa-dev-label']} htmlFor="oaa-dev-sc-url">
              Адрес sc-сервера
            </label>
            <input
              id="oaa-dev-sc-url"
              className={styles['oaa-dev-input']}
              value={scUrl}
              onChange={(event) => setScUrl(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') apply()
              }}
              spellCheck={false}
            />
          </>
        ) : (
          <>
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
          </>
        )}

        <button type="button" className={styles['oaa-dev-button']} onClick={apply}>
          Применить
        </button>

        <p className={styles['oaa-dev-hint']}>
          {kind === 'sc-memory'
            ? 'Нужны запущенные sc-machine и sc-агент (make agent). Запрос и ответ сохраняются в БЗ.'
            : 'Нужен FastAPI-сервис direct-http (make service). Режим только для отладки.'}
        </p>

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
