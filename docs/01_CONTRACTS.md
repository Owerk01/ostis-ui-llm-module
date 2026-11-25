# 01. Контракты

Контракты компонентов, действия, транспортов и форматов данных зафиксированы.
Документ готов к передаче команде на ревью; вопросы для согласования перечислены ниже.

## Read-путь не пишет в БЗ

Любой код, который только читает знания, резолвит keynodes или читает историю,
**не должен создавать, менять или удалять элементы sc-памяти**. Это правило
сильнее прежней формулировки «наши `.scs` не объявляют чужие типы».

- `ScKeynodes.resolve(idtf, sc_type)` создаёт элемент, если его нет. В пакетах
  `knowledge/` и `agents/` он запрещён; используется только `ScKeynodes.get(idtf)`.
- В панели `resolveKeynodes` получает невалидный тип `new ScType()`: если хотя бы
  одного узла нет, `ScMemoryTransport` выбрасывает ошибку «Схема ассистента не
  загружена в БЗ. Выполните make kb-load», а `health().kb.connected = false`.
- Исключение — пакет `sc/`: он владеет записью конструкций диалога и создаёт
  только наши узлы (`generate_node`, ролевые дуги `rrel_N`).
- Проверка: unit-тест сканирует `knowledge/` и `agents/`; интеграционный тест с
  маркером `kb_noschema` работает на БЗ из `platform/repo.path.assistant-only`
  (`make kb-load-noschema`) и требует, чтобы `concept_ui_button` и
  `concept_ui_visible` оставались невалидными после чтения знаний.

## Состав контракта

- существующие идентификаторы, которые только упоминаются и не переопределяются;
- новые идентификаторы ассистента (см. `service/src/ostis_ui_assistant/knowledge/identifiers.py`);
- контракт действия `action_answer_ui_development_question`;
- контракт транспортов и `AssistantPanelProps`;
- известные ограничения: мягкая отмена в режиме `sc-memory`, один экземпляр
  агента на БЗ (advisory-аренда).

## Платформа

| Параметр | Значение |
|---|---|
| sc-machine | 0.10.5, официальный prebuilt Linux x86_64 |
| sc-builder | 0.10.5 |
| Адрес | `ws://127.0.0.1:8090/ws_json` |
| Docker | не требуется |
| Схема UI | `external/ostis-ui-editor/docs/abstract_ui_model.scs` (не копируется) |
| Базовые онтологии | `external/ostis-example-app/knowledge-base` |
| Python-клиент | `py-sc-client 0.4.0`, `py-sc-kpm 0.4.0` |
| Совместимость | смоук-тест пройден на sc-machine 0.10.5 |
| Сборка БЗ | ~3 мин, 96 123 элемента; `repo.path` относительно `platform/` |

## Вопросы для согласования с командой

- [ ] Версия sc-machine: 0.10.0 или 0.10.5? Проверено на 0.10.5 с `py-sc-client 0.4.0`
  и `py-sc-kpm 0.4.0`.
- [ ] Утверждение 26 наших идентификаторов, включая T7 (коллизий с существующими нет).
- [ ] Размещение `kb/ui_assistant/` в дереве ostis-example-app (у нас подключено
  через `platform/repo.path`).
- [ ] Контракт `AssistantPanelProps` и способ встраивания (библиотечная сборка
  `npm run build:lib`, см. `panel/README.md`).
- [ ] Read-only границы: ассистент не пишет модель интерфейса.

Статус — подготовлено к передаче, ответы ожидаются.

## Отладочный транспорт direct-http

Отладочный режим (`ASSISTANT_TRANSPORT=direct-http`, см. `.env.example`).
Основной режим — `sc-memory`, описан ниже.
Сервис: FastAPI, `http://127.0.0.1:8770`, знания из `knowledge/pack.json`
(`knowledge_source = fallback`).

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/health` | модель, доступность LLM, источник знаний, версия pack, оценка токенов |
| `POST` | `/dialog` | создать диалог, вернуть `dialog_id` |
| `POST` | `/ask` | вопрос, ответ потоком SSE |
| `GET` | `/history/{dialog_id}` | история диалога в памяти сервиса |
| `POST` | `/cancel` | мягкая отмена по `message_id` |

События SSE `/ask`:

| event | data | Когда |
|---|---|---|
| `meta` | `message_id`, `dialog_id`, `state` | сразу после принятия запроса |
| `delta` | `text` | куски уже провалидированного ответа |
| `done` | `message`, `model`, `prompt_version`, `pack_version`, `latency_ms`, токены | успех |
| `cancelled` | `message` | отмена пользователем |
| `error` | `message_id`, `error`, `state` | LLM недоступна, таймаут, внутренняя ошибка |

Особенности реализации:

1. **Ответ буферизуется.** Сначала LLM генерирует текст целиком, затем он
   валидируется, и только после этого SSE отдаёт готовые куски. Потоковость
   первого токена принесена в жертву отсутствию выдуманных идентификаторов;
   первый `delta` приходит после полной генерации (~1–3 с на профиле A).
2. **Отмена в direct-http жёсткая по потоку и мягкая по смыслу.** Панель
   прерывает fetch и вызывает `/cancel`; сервис выставляет событие, генерация
   прекращается. Уже начатая генерация Ollama может дойти до конца, но результат
   не попадёт в ответ.
3. **История диалога — в памяти процесса.** Она теряется при перезапуске
   сервиса; постоянная история ведётся только в sc-памяти.
4. **Панель передаёт в `cancel()` локальный id сообщения.** `DirectHttpTransport`
   сам запоминает серверный `message_id` из события `meta` и отправляет его в
   `/cancel`. Контракт `AssistantTransport` при этом не меняется.
5. **CORS** разрешён только для `http://127.0.0.1:5173` и
   `http://localhost:5173` (dev-стенд панели). Для встраивания в редактор
   панель работает через sc-память, поэтому CORS не нужен.

## Контракт валидатора

- Регулярка распознаёт `concept_*`, `nrel_*`, `rrel_*`, `action_*` и `ui_*`
  (идентификаторы узлов знаний).
- Белый список: существующие идентификаторы ∪ новые ∪ `ENVIRONMENT_IDENTIFIERS`
  ∪ `KNOWLEDGE_IDENTIFIERS` ∪ **ключи свойств** (`PROPERTY_KEYS`). Ключ
  `action_id` совпадает с префиксом `action_*`, поэтому без ключей свойств он
  ошибочно считался бы галлюцинацией.
- Основания ответа строятся по тем же распознанным идентификаторам; idtf
  HTML-трансляции (`action_translate_sc_to_html` и др.) отображаются на узел
  `ui_env_html_representation`.
- Выдуманные `ui_*`-ссылки (например, `ui_fake_section`) не проходят whitelist
  и вырезаются из ответа с пометкой об удалении.
- `rrel_1..rrel_10` — стандартные узлы; для диалога длиннее 10 сообщений
  `dialog_store` создаёт одноимённые ролевые узлы `rrel_11+`. Валидатор разрешает
  любой `rrel_<число>`: это генерируемые нами роли, а не выдуманные идентификаторы.
- Один repair-запрос к модели, ограниченный общим дедлайном и событием отмены.
  При истечении времени или отмене repair пропускается, а неизвестные id
  вырезаются из исходного текста. Время repair пишется отдельным полем
  `repair_ms` и не смешивается с временем генерации.
- Если неизвестные остались — они вырезаются, в конец ответа добавляется
  `[часть ответа удалена: неизвестные идентификаторы]`, инцидент пишется в журнал.
- `hallucinated_id_rate` считается по наличию неизвестных **до** валидации,
  а не по финальному тексту.
- Основания ответа (`sources`) — только идентификаторы, реально поданные в
  промпт (типы, свойства, отношения из pack), а не любые слова модели.

## Боевой транспорт sc-memory

Основной режим — `ASSISTANT_TRANSPORT=sc-memory` (см. `.env.example`). Сервис не
поднимает HTTP-порт, а регистрирует sc-агент
`action_answer_ui_development_question` в sc-machine. Панель и решатель
общаются **только через БЗ**.

### Конструкции диалога

| Узел/дуга | Смысл |
|---|---|
| `concept_ui_dialog` | диалог разработчика со средой |
| `concept_ui_dialog_context` | контекст запроса (rrel_3): режим и ссылки на экземпляр интерфейса |
| `concept_ui_user_message` / `concept_ui_assistant_message` | сообщения (⊂ `concept_ui_dialog_message`) |
| `nrel_ui_dialog_message` + `rrel_1..N` | диалог → сообщение, порядок в `rrel` |
| `nrel_ui_value` (существующее) | текст сообщения в sc-link |
| `nrel_ui_id` (существующее) | стабильный id диалога `dialog-<hex>` в sc-link |
| `nrel_ui_message_time` | ISO-8601 UTC |
| `nrel_ui_message_state` | `pending` / `streaming` (зарезервирован) / `done` / `error` / `cancelled` |
| `nrel_ui_message_code` | машиночитаемый код: `pending` до ответа; после — `ok`, `busy`, `llm_unavailable`, `llm_timeout`, `invalid_request`, `cancelled`, `agent_restarted`, `schema_missing`, `schema_mismatch`, `dialog_not_found`, `internal` |
| `nrel_ui_llm_model`, `nrel_ui_prompt_version` | модель и `<версия промпта>\|pack:<ISO>` (сейчас `v4`) |
| `nrel_ui_answer_source` | ответ → узел-основание |
| `nrel_ui_knowledge_source` (существующее) | ответ → sc-link `kb` / `fallback` / `unknown` |
| `nrel_ui_dialog_context` (существующее) | user-сообщение → узел контекста запроса (T7, только режим не `none`) |
| `nrel_ui_context_mode` | контекст → sc-link `none` / `selection` / `whole` |
| `nrel_ui_context_interface` | контекст → `concept_ui_interface` |
| `nrel_ui_context_component` | контекст → компонент (повторяющееся, для выделения/подсказок) |

Новых отношений для текста не вводится: используется существующее `nrel_ui_value`.
Текст и состояние `pending`-сообщения обновляются на месте (`set_link_contents`),
поэтому один запрос даёт ровно одно assistant-сообщение.

#### Коды исхода и `retryable`

Каждое assistant-сообщение имеет `code` в `nrel_ui_message_code`. Pending-сообщение
пишется со служебным кодом `pending` (фиксированный выбор: `code` всегда заполнен),
агент перезаписывает его финальным кодом из списка:
`ok`, `busy`, `llm_unavailable`, `llm_timeout`, `invalid_request`, `cancelled`,
`agent_restarted`, `schema_missing`, `schema_mismatch`, `dialog_not_found`, `internal`.
Если у старого сообщения нет link с кодом, transports читают `ok`.
Машиночитаемый список — `contract/identifiers.json`; он же задаёт состояния
`pending | streaming | done | error | cancelled` (`streaming` пока не используется).

`AssistantMessage` панели содержит обязательные `code: OutcomeCode` и
`retryable: boolean`. `retryable` вычисляется transports из кода, а не в редакторе:
`true` только для временных ошибок `busy`, `llm_unavailable`, `llm_timeout`,
`agent_restarted`, `internal`. Остальные коды (включая `invalid_request`,
`schema_missing`, `schema_mismatch`, `dialog_not_found`, `cancelled`, `pending`)
требуют изменения вопроса/окружения или не должны повторяться автоматически.
Редактор
показывает кнопку «Повторить» **только** при `retryable === true`.

Direct-http повторяет ту же модель: `/ask` отдаёт `code` в SSE `meta`/`error`/
`cancelled` и в истории, `DirectHttpTransport` заполняет `code`/`retryable`.

Порядок сообщения вычисляется в момент добавления как `max(rrel_N) + 1` по БЗ,
а не из счётчика процесса (B0-2). `read_history` читает все значения, роли,
порядки, коды и основания пакетными запросами: число обращений к sc-памяти не
зависит от длины диалога.

### Действие

- Класс: `action_answer_ui_development_question` (⊂ `action`).
- Запуск: дуга `action_initiated → action`.
- Аргументы: `rrel_1` — sc-link с текстом вопроса; `rrel_2` — узел диалога
  (если нет, агент создаёт новый); `rrel_3` — необязательный узел
  `concept_ui_dialog_context` (контекст экземпляра интерфейса, T7).
- Результат: `nrel_result →` структура (`ScStructure`) с узлом
  `concept_ui_assistant_message`. Текст, состояние, код и основания читаются из
  самого сообщения. Результат создаётся **сразу при приёме запроса** (сообщение
  в состоянии `pending`) и не пересоздаётся при завершении. Панель читает именно
  результат действия (`action → nrel_result → структура → узел
  concept_ui_assistant_message`), а не последнее сообщение из истории; при
  отсутствии оформленного результата — ошибка «Агент завершил действие, но
  результат в БЗ не оформлен». Полная `history()` вызывается только при
  инициализации.
- Статусы: `action_finished_successfully` / `action_finished_unsuccessfully`.
- Идемпотентность: повторная доставка события проверяет `get_action_result` и
  наличие assistant-сообщения в структуре результата; при обнаружении — `SKIP`
  без записи. Проверка и создание pending-сообщения сериализованы блокировкой
  процесса, а аренда исключает конкурентный второй экземпляр.

**Важно для клиентов.** `py-sc-kpm` ищет аргументы шаблоном
`action --VAR_PERM_POS_ARC--> значение`, а `nrel`-связи — шаблоном
`источник --VAR_COMMON_ARC--> значение`. Поэтому ролевые дуги `rrel_*` должны
создаваться **perm-pos** дугой, а не common arc: иначе агент видит пустые
аргументы, создаёт новый диалог и завершает действие как `unsuccessfully`.

### Контекст экземпляра интерфейса (T7)

Режим `none | selection | whole` передаётся вместе с вопросом и не меняет
флоу без контекста. При `none` агент не читает экземпляр и не добавляет блок в
промпт; поведение совпадает с T6.

| Слой | Поле |
|---|---|
| sc-memory | `rrel_3` действия → `concept_ui_dialog_context` |
| direct-http | `POST /ask` поле `context: { mode, interface_id?, component_ids? }` |
| панель | `AskOptions.context?: DialogContextOptions` |

Узел контекста:

- `nrel_ui_context_mode` → sc-link `none` / `selection` / `whole`;
- `nrel_ui_context_interface` → `concept_ui_interface`;
- `nrel_ui_context_component` → компонент (повторяющееся);
- `nrel_ui_dialog_context` связывает узел контекста с user-сообщением (след в истории).

Read-путь читает экземпляр только через `ScKeynodes.get()` и
`search_by_template`/`search_links_by_contents`: `ScKeynodes.resolve`,
`generate_*`, `create_*` запрещены. Агент получает `interface_id`, состав по
`nrel_ui_has_component`, вложенность по `nrel_ui_contains`, связи по
`nrel_ui_input_target`/`nrel_ui_output_target`, свойства по `concept_ui_<key>` +
`nrel_ui_value`, id компонентов по `nrel_ui_id`.

Блок `ЭКЗЕМПЛЯР` добавляется отдельным system-сообщением только когда
`mode != none`. Формат компактный построчный; бюджет экземпляра 1500 токенов,
истории 800, знания 3500, резерв вывода 512, сумма 6312 < `LLM_NUM_CTX=8192`.
При усечении добавляется
`[модель интерфейса усечена: показано N из M компонентов]`; приоритет:
выделенные → соседи по связям → остальные. В лог пишутся фактические
`prompt_tokens`, `instance_tokens`, `instance_components_shown/total`,
`instance_truncated`; `near_context_limit` предупреждает при >80% `LLM_NUM_CTX`.

### Транспорт панели

`panel/src/transport/scMemory.ts` (`ScMemoryTransport`):

1. `ensureDialog(dialogId?)` создаёт узел `concept_ui_dialog` и пишет ему `nrel_ui_id`
   вида `dialog-<hex>`; `dialogId` в панели — эта строка, а не сырой `ScAddr`.
   Без `dialogId` — создаёт новый диалог; с валидным `dialogId` — открывает
   существующий (по `nrel_ui_id`) и возвращает его; невалидный/ненайденный id —
   типизированная ошибка `DialogNotFoundError` (`dialog_not_found`), новый
   диалог не создаётся молча.
2. `ask(dialogId, question, options?)` создаёт действие: `rrel_1` — текст,
   `rrel_2` — диалог, `rrel_3` — узел `concept_ui_dialog_context`, если
   `options.context.mode !== 'none'`. При неизвестном id диалога — типизированная
   ошибка `DialogNotFoundError` (`dialog_not_found`), диалог не подменяется.
   Плоская форма `ask(dialogId, question, onDelta?, signal?)` сохраняется для
   совместимости.
3. Ожидание — подписка `AfterGenerateIncomingArc` на узел действия плюс
   опрос `action_finished` каждые 400 мс; клиентский таймаут 35 с из
   `DIALOG_CLIENT_TIMEOUT_S` / `VITE_DIALOG_CLIENT_TIMEOUT_S` (не хардкодится).
4. Ответ читается из результата действия: текст, состояние, код, время, модель,
   версия промпта, основания (`SourceRef`).
5. `cancel()` — **мягкая отмена**: панель перестаёт ждать и помечает сообщение
   «Отменено», агент дописывает ответ в БЗ; при перезагрузке страницы ответ
   появится в истории.
6. Стриминга нет: `onDelta` вызывается один раз с полным текстом после записи
   в БЗ.
7. Контекст T7: `AskOptions.context = { mode: 'none' | 'selection' | 'whole',
   interfaceId?, componentIds? }`. Панель передаёт только выбор пользователя;
   агент читает экземпляр из sc-памяти на чтение через `ScKeynodes.get()` и
   `search_by_template`, не создавая узлы/связи. При `mode=selection` в промпт
   попадают выделенные компоненты; при `mode=whole` добавляются соседи по
   `nrel_ui_input_target`/`nrel_ui_output_target`/`nrel_ui_contains`.
   `mode=none` не добавляет блок экземпляра и не меняет поведение промпта.
7. Исходы ожидания — типизированные ошибки вместо строковых: `AssistantTimeout`
   (с `actionId` и `dialogId`), `AssistantCancelled`, `AssistantSchemaMissing`,
   `AssistantDialogNotFound`, `AssistantBusy`. Их коды зафиксированы в
   `contract/identifiers.json` (`transportErrors`).
8. `readActionResult(actionId)` дочитывает уже оформленный результат действия
   **без повторной отправки вопроса**; `null`, если действие ещё не завершено.

### Таймаут ожидания и поздний результат

Клиентский лимит (1 с в тесте, 35 с в проде) истёк, а агент ещё пишет ответ —
`ask()` бросает `AssistantTimeout` с `actionId` действия. Панель сохраняет этот
`actionId`, оставляет **одно** assistant-сообщение в состоянии `pending` и
показывает «Ответ ещё готовится» + кнопку «Проверить». По нажатию вызывается
`readActionResult(actionId)`: если результат появился, лента обновляется
готовым сообщением; новый вопрос не создаётся, вторая пара сообщений не
добавляется. Если ответ ещё не готов, баннер остаётся и проверку можно повторить.

Мягкая отмена (`cancel()` / `AbortSignal`) использует тот же принцип: поток
ожидания прерывается типизированным `AssistantCancelled`, конструкции БЗ и
уже созданные сообщения не удаляются. На каждый ход приходится ровно одно
user- и одно assistant-сообщение; тест `test_late_result_recoverable` проверяет
это для таймаута, а `мягкая отмена не создаёт второй ход` — для отмены.

### Восстановление диалога после F5 (T2)

- Ответственность за идентификатор: **редактор**. Модуль (транспорт/агент) хранит
  только БЗ; id диалога живёт у редактора (`sessionStorage`, привязка к открытому
  интерфейсу, ключ вида `dialogId:<interfaceId>`).
- Стартовая последовательность при монтировании панели/транспорта:
  `health()` → `ensureDialog(savedId)` → `history(savedId)`.
- `ensureDialog(dialogId?)`:
  - без аргумента — создать новый диалог (в т.ч. при первом запуске);
  - с валидным id — открыть существующий и вернуть его;
  - с невалидным/ненайденным id — **не создавать молча**: бросает
    `DialogNotFoundError` (`dialog_not_found`).
- `ask(dialogId, …)`: не должен подменять диалог — неизвестный id даёт
  `DialogNotFoundError`; известный id обслуживает существующий диалог.

### /health в режиме sc-memory (T4)

`GET /health` доступен только в `direct-http`. В sc-режиме `ScMemoryTransport.health()`
читает узел состояния сервиса `concept_ui_dialog_service` (связи
`nrel_ui_service_state` / `nrel_ui_service_heartbeat`) и возвращает как минимум:
`schemaLoaded`, `agentAlive` (heartbeat свежее `service_lease_ttl_s`), `state`
(`starting|ready|degraded|busy|stopping|stopped`), `model`, `packVersion`,
`promptVersion`, `knowledgeSource`, `queueDepth`, `contractVersion`. Fallback
через историю (`healthFromMessages`) остаётся только если узел состояния недоступен.
Поля `llm`/`kb` сохранены для обратной совместимости; миграции не требуется.

`KnowledgeService.health()` (direct-http) отдаёт те же поля из `ServiceState`,
который передаётся в конструктор, плюс `timeouts` с фактическими значениями
`llmTimeoutS` и `dialogClientTimeoutS`.

`AssistantHealth.kb.knowledgeSource` принимает `'kb' | 'fallback' | 'unknown'`,
`AssistantHealth.llm.model` — `string | null`. Поля `kb.connected`,
`kb.knowledgeSource`, `kb.partial`, `kb.missing` в `KnowledgeService.health()`
заполняются из `KbStatus`.

**Правило для редактора:** нет схемы ассистента (`schemaLoaded === false`) → чат
не показываем; схема есть, агент не жив (`agentAlive === false`) → чат показываем,
ввод заблокирован, баннер «Агент диалога не запущен» и подсказка
`make agent-start`. До первого ответа статус берётся из узла сервиса, а не из
истории сообщений. `keynodes()` остаётся search-only и при отсутствии узлов
бросает понятную ошибку «Схема ассистента не загружена в БЗ…».

### Потоки, очередь и таймауты (B0-1)

`UiDialogAgent.on_event` только валидирует аргументы, создаёт
пользовательское сообщение, pending-сообщение ассистента и результат действия,
после чего кладёт задачу в `DialogWorker` и возвращает управление. Генерация
LLM в обработчике события не выполняется.

| Что | Значение по умолчанию | Настройка |
|---|---|---|
| Воркеры генерации | 1 (допустимо 1–2) | `DIALOG_WORKER_THREADS` |
| Очередь запросов | 16 | `DIALOG_QUEUE_SIZE` |
| Интерактивный таймаут LLM | 25 с (< 30 с у редактора) | `LLM_TIMEOUT_S` |
| Клиентский таймаут ожидания (strict > LLM_TIMEOUT_S) | 35 с | `DIALOG_CLIENT_TIMEOUT_S` / `VITE_DIALOG_CLIENT_TIMEOUT_S=35000` |
| Таймаут eval | 120 с | `LLM_TIMEOUT_S_BATCH` |
| Heartbeat сервиса | каждые 5 с | `SERVICE_HEARTBEAT_INTERVAL_S` |
| Протухание аренды | 20 с | `SERVICE_LEASE_TTL_S` |

При переполнении очереди запрос не ждёт: pending-сообщение сразу переводится в
`error` с кодом `busy`, действие завершается `action_finished_unsuccessfully`.

Бюджет потоков sc-machine: наш сервис занимает один краткоживущий поток
обработчика события sc-client на каждое событие (возвращается за единицы мс),
1–2 воркера генерации и 1 поток heartbeat. Поток sc-machine не удерживается на
время LLM-запроса. Для совместной работы с редактором и транслятором в
`platform/sc-machine.ini` задано `max_events_and_agents_threads = 32`; меньше 16
для общего стенда не рекомендуется. `parallel_actions = true`.

При старте watchdog находит initiated-действия нашего класса без
`action_finished`, переводит связанное pending-сообщение в `error` с кодом
`agent_restarted` и завершает действие `action_finished_unsuccessfully`.

### Один экземпляр на БЗ (B0-2)

Узел `concept_ui_dialog_service` — единственный узел состояния сервиса. При
старте агент читает `nrel_ui_service_state` (JSON) и
`nrel_ui_service_heartbeat` (ISO-8601). Если heartbeat свежее
`SERVICE_LEASE_TTL_S` и состояние не `stopped`, второй экземпляр **отказывается
регистрироваться** и завершается с ненулевым кодом:

```text
Агент уже запущен (instance …), второй экземпляр не допускается
```

Heartbeat обновляется фоновым потоком раз в 5 с. При корректной остановке
состояние переводится в `stopped`, и аренда освобождается. Это **advisory-
механизм, а не распределённая блокировка**: он защищает от случайного второго
`make agent`, но не от гонки двух процессов в один и тот же момент старта.
Поэтому порядок сообщений дополнительно вычисляется из БЗ, а не из счётчика
процесса.

## Качество и guard идентификаторов

- Рабочий промпт — `knowledge/prompt_v4.md`, версия в журнале и БЗ — `v4`.
  В `nrel_ui_prompt_version` пишется строка `v4|pack:<ISO-время сборки>`.
- **Санитизация вопроса.** Неизвестный системный идентификатор заменяется на
  «неизвестный идентификатор», после чего вопрос **всё равно уходит в LLM**.
  В журнале `guard = "sanitized"`, исходный текст в БЗ и JSONL не меняется.
  Детерминированный отказ (`guard = "unknown_identifier"`) — только если после
  санитизации не осталось содержательной части.
- `ENVIRONMENT_IDENTIFIERS` (`action_translate_sc_to_html`,
  `nrel_html_representation`, `concept_current_ostis_ui_model`) — идентификаторы
  среды, которые мы только упоминаем и не объявляем в своих `.scs`. Источник —
  `external/ostis-ui`, `HTMLTranslatorKeynodes.hpp` (см. provenance). Валидатор
  считает их допустимыми.
- `/health` (direct-http) дополнительно отдаёт `prompt_version`,
  `knowledge_estimated_tokens`, `kb.partial`, `kb.missing`, `sc_connected`.

### Контракт знаний

- **16 типов, 27 свойств.** `action_id` доступен только типам-источникам
  действий: `concept_ui_button`, `concept_ui_select`, `concept_ui_menu_item`.
  У остальных 13 типов 26 общих свойств; правило задаётся `allowed_props` в
  `catalog.ts` и повторяется в `knowledge/pack.json`.
- **6 отношений.** `nrel_ui_contains` — вложенность без ограничений по типам;
  `nrel_ui_input_target` — «триггер → откуда читать» (источники `button`,
  `select`, `menu_item`; цели `text_field`, `text_area`, `select`, `slider`);
  `nrel_ui_output_target` — «триггер → куда писать результат» (источники те же,
  13 целей из `OUTPUT_TARGET_TYPES`); также `nrel_ui_has_component`,
  `nrel_ui_id`, `nrel_ui_value`.
- **Источник истины — код редактора**, а не `docs/catalog.md`: `catalog.ts`,
  `linkRules.ts`, `names.ts`, `types.ts`, `i18n/ru.ts`. `make drift` входит в
  `make test` и падает при расхождении типов/свойств/отношений,
  `allowed_props`, наборов источников/целей, whitelist с upstream или пинов
  `provenance.json`. Расхождение `catalog.md` с кодом — отдельный WARN.
- **Удалённые идентификаторы.** `nrel_html_template`, `nrel_html_parameter_id`,
  `nrel_sc_template`, `rrel_specific_realisation` больше не входят в whitelist
  и не упоминаются в знаниях; тест `test_no_stale_environment_identifiers`
  падает при их возврате.

### Определения метрик

| Метрика | Определение | Порог |
|---|---|---|
| `accuracy` | доля вопросов, прошедших автопроверки | информационная |
| `hallucinated_id_rate` | доля ответов с неизвестным id **до** валидации | информационная |
| `unknown_id_in_final_rate` | доля финальных ответов с неизвестным id | **0** |
| `refusal_correctness` | точность на negative/out_of_scope | ≥ 0.90 |
| `injection_resistance` | доля инъекций без выполнения инструкции и без неизвестных id (≥ 5 вопросов) | ≥ 0.90 |
| `factual_accuracy` | `correct / total` по ручной разметке | ≥ 0.90 |
| `incorrect_count` | число ответов с verdict `incorrect` | 0 (цель) |

Dev и holdout публикуются раздельно; warm/cold latency замеряются отдельно.
Фактические числа и невыполненные пороги — `docs/03_EVAL.md`.

### Статистика LLM

- Оба бэкенда сбрасывают `LLMStats()` в начале `chat()`: после таймаута в журнал
  не попадают токены предыдущего запроса.
- OpenAI-бэкенд запрашивает `stream_options={"include_usage": True}` и читает
  `usage` из финального chunk без `choices`. Если провайдер не вернул usage,
  в журнал пишется `tokens_unavailable: true` (а не достоверные нули).
- Параметр лимита вывода: сначала `max_tokens`, при ошибке — откат на
  `max_completion_tokens`; то же для `stream_options` (откат без него с пометкой
  `tokens_unavailable`). Поведение задокументировано в `.env.example`.
- Оценка рендера `len/3` калибруется по фактическому `prompt_eval_count`:
  если факт превышает 80% `LLM_NUM_CTX`, сервис пишет WARN, а отчёт eval
  показывает обе величины и число предупреждений.

## Известные ограничения

- `mode=whole` при больших интерфейсах ограничен бюджетом 1500 токенов на блок
  экземпляра; полный интерфейс не передаётся. Приоритет: выделенные компоненты,
  затем соседи по связям, затем остальные. Усекаемый хвост помечается маркером.

| Ограничение | Причина | План |
|---|---|---|
| Стрим только после полной генерации | приоритет — отсутствие выдуманных идентификаторов | при необходимости |
| Мягкая отмена в sc-memory | у панели нет канала, чтобы прервать LLM внутри агента | жёсткая отмена через маркер в БЗ |
| `on_event` блокирует поток sc-событий до генерации | синхронный обработчик py-sc-kpm | **решено (B0-1)**: очередь воркеров + клиентский таймаут 35 с с дочиткой результата |
| Два экземпляра агента на одну БЗ | check-then-act по `nrel_result`, расхождение `rrel_N` | **решено (B0-2)**: аренда в узле состояния, ordinal из БЗ, идемпотентность по результату+сообщению |
| Нет стриминга в sc-memory | семантика ответа живёт в БЗ, канал отдельный | отдельный SSE-канал |
| Один диалог на вкладку | `ensureDialog()` создаёт новый узел без `dialogId` | **решено (T2)**: `ensureDialog(dialogId?)` открывает существующий по `nrel_ui_id`; редактор хранит id (`sessionStorage`, ключ `dialogId:<interfaceId>`) и передаёт при старте (`health → ensureDialog(savedId) → history(savedId)`) |
| Один активный запрос на транспорт | защита от гонок UI | очередь воркеров |
| Повтор unsuccessful-ответа | создаёт **новый полный ход**: пользовательское сообщение добавляется и в БЗ, и локально; прежний ход остаётся в истории | — |
| Профиль C `gemma4:e4b` не принят | refusal 83.3% < 90% | рабочий A, альтернатива B |
