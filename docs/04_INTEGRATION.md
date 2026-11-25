# 04. Интеграция

Документ описывает только те части контракта, которые нужны для совместного
запуска с редактором и транслятором. Полная форма действия и история — в
`docs/01_CONTRACTS.md`.

## Один экземпляр на БЗ

На одну sc-память должен работать **один** экземпляр агента
`action_answer_ui_development_question`.

- При старте агент читает узел `concept_ui_dialog_service`:
  `nrel_ui_service_state` (JSON) и `nrel_ui_service_heartbeat` (ISO-8601).
- Если heartbeat свежее `SERVICE_LEASE_TTL_S` (по умолчанию 20 с), а состояние
  не `stopped`, второй экземпляр пишет в лог
  «Агент уже запущен (instance …), второй экземпляр не допускается» и
  завершается с ненулевым кодом, **не регистрируя обработчик**.
- Heartbeat обновляется раз в `SERVICE_HEARTBEAT_INTERVAL_S` (5 с).
- При корректной остановке состояние переводится в `stopped`, аренда
  освобождается. После аварийного завершения нужно подождать TTL (20 с) или
  перезапустить БЗ.

Это **advisory-аренда**, а не распределённая блокировка. Она защищает от
случайного второго `make agent`, но не от одновременного старта двух процессов.
Поэтому:

- порядок сообщений вычисляется из БЗ (`max(rrel_N) + 1`), а не из счётчика
  процесса;
- повторная доставка события отсекается по `nrel_result` и assistant-сообщению.

Если аренду обойти, оба процесса обработают одно действие: получится два
ответа, два набора оснований и дубли `rrel_N` в одном диалоге.

## Форма результата

```text
action --nrel_result--> structure --perm-pos--> concept_ui_assistant_message
```

Текст, состояние (`pending`/`done`/`error`/`cancelled`), код исхода, модель,
версия промпта и основания читаются из узла сообщения:

- `nrel_ui_value` — текст;
- `nrel_ui_message_state` — состояние;
- `nrel_ui_message_code` — `pending` до ответа, затем один из
  `ok`, `busy`, `llm_unavailable`, `llm_timeout`, `invalid_request`, `cancelled`,
  `agent_restarted`, `schema_missing`, `schema_mismatch`, `dialog_not_found`, `internal`.
  Список продублирован в `contract/identifiers.json`. Транспорт заполняет
  `AssistantMessage.code` и `retryable` (только для `busy`, `llm_unavailable`,
  `llm_timeout`, `agent_restarted`, `internal`); «Повторить» показываем по флагу;
- `nrel_ui_llm_model`, `nrel_ui_prompt_version`, `nrel_ui_knowledge_source`;
- `nrel_ui_answer_source` — узлы-основания: классы каталога и, при контексте
  экземпляра, интерфейс/компоненты, упомянутые в финальном ответе.

Результат создаётся сразу при приёме запроса, поэтому клиент может показать
`pending` до завершения генерации. После `action_finished` сообщение уже
содержит финальный текст и состояние.

Если клиентский таймаут истёк раньше агента, `ask()` бросает
`AssistantTimeout` с `actionId` (код `assistant_timeout` в
`contract/identifiers.json`). Панель показывает «Ответ ещё готовится» и кнопку
«Проверить»; обработчик вызывает `transport.readActionResult(actionId)` и
заменяет то же самое pending-сообщение готовым — повторный вопрос не шлётся и
вторую пару сообщений не создаёт. Остальные исходы ожидания тоже типизированы:
`AssistantCancelled`, `AssistantSchemaMissing`, `AssistantDialogNotFound`,
`AssistantBusy`. Мягкая отмена не удаляет конструкции в БЗ: на ход по-прежнему
одно user- и одно assistant-сообщение.

## Таймауты и потоки

| Параметр | Значение | Переменная |
|---|---|---|
| Интерактивный таймаут LLM | `LLM_TIMEOUT_S=25` с | `LLM_TIMEOUT_S` |
| Клиентский таймаут ожидания (strict > LLM_TIMEOUT_S) | `DIALOG_CLIENT_TIMEOUT_S=35` с | `DIALOG_CLIENT_TIMEOUT_S` / `VITE_DIALOG_CLIENT_TIMEOUT_S=35000` |
| Таймаут eval | `LLM_TIMEOUT_S_BATCH=120` с | `LLM_TIMEOUT_S_BATCH` |
| Очередь запросов | `DIALOG_QUEUE_SIZE=16` | `DIALOG_QUEUE_SIZE` |
| Воркеры генерации | `DIALOG_WORKER_THREADS=1` (1–2) | `DIALOG_WORKER_THREADS` |
| `max_events_and_agents_threads` | 32 в `platform/sc-machine.ini` (минимум 16) | — |

Правило: клиент ждёт дольше, чем генерирует LLM (`DIALOG_CLIENT_TIMEOUT_S > LLM_TIMEOUT_S`),
проверяется при старте сервиса. Редактор ждёт агента 30 000 мс (previewHtml.ts), поэтому
интерактивный таймаут LLM (25 с) укладывается в этот предел.

`on_event` возвращает управление за единицы миллисекунд и не держит поток
событий sc-machine на время LLM-запроса. При переполнении очереди действие
завершается `action_finished_unsuccessfully`, сообщение получает код `busy`.

## Минимальный пример на Python

```python
from sc_kpm.utils.action_utils import execute_agent, get_action_result
from sc_kpm.utils import generate_link

action, ok = execute_agent(
    arguments={generate_link("Что такое concept_ui_button?"): False},
    concepts=["action_answer_ui_development_question"],
    wait_time=30,
)
assert ok
structure = get_action_result(action)
# далее structure -> perm-pos -> concept_ui_assistant_message -> nrel_ui_value
```

## Минимальный пример на TypeScript

Транспорт вынесен в отдельный пакет без React:

```bash
cd panel && npm run build:transport
# артефакт: panel/dist-transport/ (package.json, index.js, *.d.ts)
```

`ts-sc-client` остаётся peerDependency; React в зависимостях пакета нет.
Полный живой пример без React — `tools/integration-check.ts`
(`make integration-check`, флаг `--build-only` проверяет только сборку).

```ts
import {
  ScClient,
  ScMemoryTransport,
  DEFAULT_SC_URL,
  CONTRACT_VERSION,
  AssistantTimeout,
  AssistantBusy,
  AssistantCancelled,
  AssistantSchemaMissing,
  AssistantDialogNotFound,
  isRetryable,
  isStableDialogId,
  type AssistantTransport,
  type AssistantMessage,
  type OutcomeCode,
} from 'ostis-ui-assistant-dialog-transport'

// Конструктор сам открывает WebSocket; метода connect() у ts-sc-client нет.
const client = new ScClient(DEFAULT_SC_URL)
await new Promise<void>((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('sc-machine недоступен')), 5000)
  client.addEventListener('open', () => { clearTimeout(timer); resolve() })
  client.addEventListener('error', () => { clearTimeout(timer); reject(new Error('sc-machine недоступен')) })
})
const transport: AssistantTransport = new ScMemoryTransport(client, 35_000)

// 1. health: схема, версии, живой агент.
const health = await transport.health()
if (health.schemaLoaded === false) {
  throw new Error('Схема ассистента не загружена в БЗ: выполните make kb-load')
}
if (health.contractVersion !== CONTRACT_VERSION) {
  throw new Error(`Несовместимая версия контракта: ${health.contractVersion}`)
}
if (health.agentAlive === false || !health.llm.reachable) {
  // Чат показываем, но ввод блокируем и показываем баннер.
  console.warn('Агент диалога не запущен: make agent-start')
}

// 2. ensureDialog(savedId): редактор хранит id в sessionStorage по interfaceId.
const savedId: string | undefined = undefined
const dialogId = savedId && isStableDialogId(savedId)
  ? await transport.ensureDialog(savedId)
  : await transport.ensureDialog()

// 3. history: предыдущие ходы восстанавливаются после F5.
const history: AssistantMessage[] = await transport.history(dialogId)
history.forEach((message) => handleOutcome(message.code))

// 4. ask(context): контекст экземпляра передаёт редактор, а не транспорт.
function handleOutcome(code: OutcomeCode): void {
  switch (code) {
    case 'ok':
      return
    case 'pending':
      // Сообщение ещё генерируется: ждём или вызываем readActionResult.
      return
    case 'busy':
    case 'llm_unavailable':
    case 'llm_timeout':
    case 'agent_restarted':
    case 'internal':
      console.warn(`${code}: можно повторить вопрос`)
      return
    case 'invalid_request':
    case 'cancelled':
    case 'schema_missing':
    case 'schema_mismatch':
    case 'dialog_not_found':
      console.error(`${code}: повтор без изменений не поможет`)
      return
  }
}

const options = {
  context: {
    mode: 'selection' as const,
    interfaceId: 'ex_login',
    componentIds: ['ex_login_cmp_10'],
  },
}
let answer: AssistantMessage
try {
  answer = await transport.ask(dialogId, 'Что делает эта кнопка?', options)
} catch (error) {
  if (error instanceof AssistantTimeout) {
    // 5a. Не шлём вопрос повторно: дочитываем то же действие.
    const late = await transport.readActionResult(error.actionId)
    if (!late) throw error
    answer = late
  } else if (
    error instanceof AssistantBusy ||
    error instanceof AssistantCancelled ||
    error instanceof AssistantSchemaMissing ||
    error instanceof AssistantDialogNotFound
  ) {
    throw error
  } else {
    throw error
  }
}
handleOutcome(answer.code)
console.log(answer.text, answer.sources, isRetryable(answer.code))

// 5b. Мягкая отмена: перестаём ждать, конструкции в БЗ не трогаем.
const controller = new AbortController()
const pending = transport.ask(dialogId, 'Отменённый вопрос', {
  signal: controller.signal,
})
controller.abort()
await transport.cancel('')
await pending.catch(() => undefined)
```

Кнопка «Новый диалог» создаёт свежий id (`ensureDialog()` без аргумента).
Клиент ждёт `action_finished` не дольше 35 с (`DIALOG_CLIENT_TIMEOUT_S`,
`VITE_DIALOG_CLIENT_TIMEOUT_S`) — больше чем LLM (25 с) и меньше чем 30 с у
`previewHtml.ts`.

## Матрица совместимости

| Компонент | Версия / контракт | Что важно |
|---|---|---|
| Наш transports ↔ схема редактора | контракт `0.2.0` (`VERSION`, `contractVersion`, `v4\|contract:0.2.0\|pack:<ISO>`) | добавление полей — minor, изменение смысла — major; сверяйте `health.contractVersion` перед вызовом `ask` |
| sc-machine | 0.10.5, C++20 | `parallel_actions = true`, `max_events_and_agents_threads ≥ 16` (в репозитории 32) |
| `ostis-ui-editor` | `previewHtml.ts`, ожидание 30 000 мс | наш клиентский таймаут 35 с и LLM 25 с согласованы |
| `ostis-ui` (транслятор) | `action_translate_sc_to_html` | агент не вызывает и не изменяет его ключевые узлы |
| `UI-adaptation` | контракт A/B/C | единственный писатель — один экземпляр нашего агента на БЗ |
| `ts-sc-client` / `py-sc-kpm` | 0.5.0 / sc-machine 0.10.x | результат действия — `nrel_result → структура → сообщение` |
| `ostis-ui-assistant-dialog-transport` | `0.2.0` | standalone-пакет, peerDependency только `ts-sc-client` |

## Что модуль не делает

- не изменяет модель интерфейса;
- не вызывает `action_translate_sc_to_html`;
- вопросы о конкретном разрабатываемом интерфейсе поддерживаются только при
  переданном контексте экземпляра (`mode=selection|whole`); без контекста агент
  отвечает по каталогу/методике, но не читает модель интерфейса из БЗ;
- панель не сканирует sc-память сама: выбор интерфейса и компонентов передаёт
  редактор через `AssistantPanelProps.context`.
