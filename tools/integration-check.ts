/**
 * Внешний минимальный клиент транспорта без React.
 *
 * Живой прогон (нужны sc-machine, агент и LLM):
 *   make up
 *   make integration-check
 *   Q="Что такое concept_ui_button?" node --experimental-strip-types tools/integration-check.ts
 *
 * Только проверка собранного пакета (без БЗ):
 *   node --experimental-strip-types tools/integration-check.ts --build-only
 */

import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const dist = resolve(root, 'panel', 'dist-transport')

const version = readFileSync(resolve(root, 'VERSION'), 'utf8').trim()
const pkg = JSON.parse(readFileSync(resolve(dist, 'package.json'), 'utf8'))
const bundle = readFileSync(resolve(dist, 'index.js'), 'utf8')

function assert(condition: unknown, message: string): void {
  if (!condition) throw new Error(message)
}

function checkBuild(transport: Record<string, any>): void {
  assert(pkg.version === version, `VERSION=${version}, пакет=${pkg.version}`)
  assert(!pkg.dependencies, 'у транспорта не должно быть runtime-зависимостей')
  const peers = Object.keys(pkg.peerDependencies ?? {})
  assert(
    peers.length === 1 && peers[0] === 'ts-sc-client',
    `peerDependencies: ожидается только ts-sc-client, получено ${peers.join(', ')}`,
  )
  assert(!/from ["']react/.test(bundle), 'в бандле есть импорт React')
  assert(transport.CONTRACT_VERSION === version, 'контракт в TS отличается от VERSION')

  const required = [
    'ScClient',
    'ScMemoryTransport',
    'DEFAULT_SC_URL',
    'AssistantBusy',
    'AssistantCancelled',
    'AssistantDialogNotFound',
    'AssistantSchemaMissing',
    'AssistantTimeout',
    'DialogNotFoundError',
    'isRetryable',
    'toOutcomeCode',
    'isStableDialogId',
    'newDialogId',
  ]
  for (const name of required) {
    assert(name in transport, `не экспортируется ${name}`)
  }
  console.log(`BUILD OK: transport ${version}, React в зависимостях нет`)
}

/** Каждый код исхода из contract/identifiers.json обрабатывается явно. */
function handleOutcome(code: string): void {
  switch (code) {
    case 'ok':
      console.log('OUTCOME ok: ответ готов')
      return
    case 'pending':
      throw new Error('pending: ответ ещё не завершён, вызовите readActionResult')
    case 'busy':
    case 'llm_unavailable':
    case 'llm_timeout':
    case 'agent_restarted':
    case 'internal':
      console.log(`OUTCOME ${code}: временная ошибка, можно повторить вопрос`)
      return
    case 'invalid_request':
    case 'cancelled':
    case 'schema_missing':
    case 'schema_mismatch':
    case 'dialog_not_found':
      console.log(`OUTCOME ${code}: повтор без изменений не поможет`)
      return
    default:
      throw new Error(`Неизвестный код исхода: ${code}`)
  }
}

/** ts-sc-client открывает WebSocket в конструкторе, метода connect() нет. */
function waitForOpen(client: any): Promise<void> {
  return new Promise((resolveOpen, rejectOpen) => {
    const timer = setTimeout(
      () => rejectOpen(new Error('sc-machine недоступен: выполните make up')),
      5000,
    )
    const done = (error?: Error): void => {
      clearTimeout(timer)
      if (error) rejectOpen(error)
      else resolveOpen()
    }
    client.addEventListener('open', () => done())
    client.addEventListener('error', () =>
      done(new Error('sc-machine недоступен: выполните make up')),
    )
  })
}

async function main(): Promise<void> {
  const transport = (await import('../panel/dist-transport/index.js')) as Record<string, any>
  checkBuild(transport)
  if (process.argv.includes('--build-only')) return

  const {
    ScClient,
    ScMemoryTransport,
    DEFAULT_SC_URL,
    AssistantTimeout,
    AssistantBusy,
    AssistantCancelled,
    AssistantDialogNotFound,
    AssistantSchemaMissing,
    isStableDialogId,
    isRetryable,
  } = transport

  const client = new ScClient(process.env.SC_WS_URL ?? DEFAULT_SC_URL)
  await waitForOpen(client)
  const assistant = new ScMemoryTransport(client, 35_000)

  try {
    // 1. health: схема, версия контракта, живой агент.
    const health = await assistant.health()
    assert(health.schemaLoaded !== false, 'Схема ассистента не загружена: make kb-load')
    assert(health.contractVersion === version, `Версия контракта в БЗ: ${health.contractVersion}`)
    if (health.agentAlive === false || !health.llm.reachable) {
      throw new Error('Агент диалога не запущен: make agent-start')
    }

    // 2. ensureDialog(savedId): редактор хранит id в sessionStorage.
    const savedId = process.env.DIALOG_ID
    const dialogId =
      savedId && isStableDialogId(savedId)
        ? await assistant.ensureDialog(savedId)
        : await assistant.ensureDialog()
    console.log(`DIALOG ${dialogId}`)

    // 3. history: предыдущие ходы доступны после F5.
    const history = await assistant.history(dialogId)
    console.log(`HISTORY ${history.length} сообщений`)
    for (const message of history) handleOutcome(message.code)

    // 4. ask(context): контекст экземпляра задаёт редактор.
    const question = process.env.Q ?? 'Что такое concept_ui_button?'
    const options = process.env.EX_INTERFACE_ID
      ? {
          context: {
            mode: process.env.EX_MODE ?? 'selection',
            interfaceId: process.env.EX_INTERFACE_ID,
            componentIds: (process.env.EX_COMPONENTS ?? '').split(',').filter(Boolean),
          },
        }
      : undefined

    let answer
    try {
      answer = await assistant.ask(dialogId, question, options)
    } catch (error) {
      // 5a. Таймаут: не шлём вопрос повторно, дочитываем то же действие.
      if (error instanceof AssistantTimeout) {
        console.log(`TIMEOUT ${error.code}: читаем действие ${error.actionId}`)
        const late = await assistant.readActionResult(error.actionId)
        assert(late, 'Действие ещё не завершено; повторите проверку позже')
        answer = late
      } else if (
        error instanceof AssistantBusy ||
        error instanceof AssistantCancelled ||
        error instanceof AssistantDialogNotFound ||
        error instanceof AssistantSchemaMissing
      ) {
        throw error
      } else {
        throw error
      }
    }

    handleOutcome(answer.code)
    console.log(`RETRYABLE ${isRetryable(answer.code)}`)
    assert(answer.state === 'done', `Незавершённое сообщение: ${answer.state}`)
    assert(answer.text.trim().length > 0, 'Пустой ответ из БЗ')
    console.log(`ANSWER ${answer.text}`)

    // 5b. Мягкая отмена: перестаём ждать, конструкции в БЗ не трогаем.
    if (process.env.INTEGRATION_CANCEL_DEMO === '1') {
      const controller = new AbortController()
      const pending = assistant.ask(dialogId, 'Отменённый вопрос', {
        signal: controller.signal,
      })
      controller.abort()
      await assistant.cancel('')
      await pending.catch(() => undefined)
      console.log('CANCEL OK')
    }
  } finally {
    ;(client as any)._socket?.close?.()
  }
}

main().catch((error: unknown) => {
  console.error(error instanceof Error ? error.message : error)
  process.exitCode = 1
})
