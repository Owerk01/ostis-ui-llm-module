# Changelog

## Unreleased

### T9: история диалога в промпте

- Последние `DIALOG_HISTORY_TURNS` завершённых сообщений (по умолчанию 6)
  передаются в сервис и добавляются после few-shot обычными turns
  `user`/`assistant`; текущий вопрос, pending и ошибки исключаются.
- Бюджет истории 800 токенов, усечение с начала; знания и блок экземпляра
  сохраняют свои бюджеты. Контракт и README прямо описывают историю как
  контекст последних ходов, а не долговременную память.

### T7: контекст экземпляра интерфейса в запросе

- `action_answer_ui_development_question` принимает `rrel_3` — узел
  `concept_ui_dialog_context` с `nrel_ui_context_mode` (`none|selection|whole`),
  `nrel_ui_context_interface` и повторяющимся `nrel_ui_context_component`;
  user-сообщение связывается с контекстом через `nrel_ui_dialog_context`.
- Транспорт панели принимает `ask(dialogId, question, options?)`, где
  `options.context` задаёт режим/интерфейс/компоненты; плоские
  `onDelta`/`signal` сохранены для совместимости. Direct-http принимает
  `context` в `/ask`.
- Агент читает экземпляр только на чтение (`ScKeynodes.get`, шаблоны поиска):
  интерфейс по `nrel_ui_id`, состав по `nrel_ui_has_component`, вложенность по
  `nrel_ui_contains`, связи по `nrel_ui_input_target`/`nrel_ui_output_target`,
  свойства по `concept_ui_<key>` + `nrel_ui_value`.
- Блок `ЭКЗЕМПЛЯР` добавляется отдельным system-сообщением только при
  `mode != none`; `prompt_v4.md` и gold-заморозка не менялись. Бюджеты: знания
  3500, история 800, экземпляр 1500, резерв вывода 512; усечение помечается
  `[модель интерфейса усечена: показано N из M компонентов]`.
- Тесты: чтение экземпляра без `generate_*`, формат/усечение 200 компонентов,
  приоритет selection, none-регрессия промпта, прокидывание контекста через
  агент/воркер/direct-http и нормализация AskOptions в панели.

### T8: идентификаторы экземпляра в валидаторе и основаниях

- Второй класс идентификаторов (`ex_*`, `*_cmp_*`) проверяется не по whitelist,
  а по id, прочитанным из БЗ в этом запросе. `ex_*` из вопроса сохраняется как
  цитата, но без чтения из БЗ не становится основанием; `cmp_*` без экземпляра
  вырезается с пометкой.
- `answer.sources` включает узлы интерфейса и компонентов, если их id попал в
  финальный текст; воркер разрешает такие узлы через `nrel_ui_id` прочитанного
  экземпляра и пишет `nrel_ui_answer_source`.
- В отчёте eval добавлены раздельные `unknown_catalog_in_final_rate` и
  `unknown_instance_in_final_rate`. Пороги и заморозка gold не менялись.

### T6: типизированные исходы ожидания и дочитка позднего результата

- Введены `AssistantTimeout` (с `actionId`/`dialogId`), `AssistantCancelled`,
  `AssistantSchemaMissing`, `AssistantDialogNotFound`, `AssistantBusy` вместо
  строковых `Error`; коды зафиксированы в `contract/identifiers.json`.
- Новый `AssistantTransport.readActionResult(actionId)` читает готовый результат
  по actions в sc-памяти и по истории в direct-http, не отправляя вопрос повторно.
- При таймауте панель оставляет одно pending-сообщение, показывает «Ответ ещё
  готовится» и кнопку «Проверить»; найденный результат заменяет это сообщение.
- Мягкая отмена не создаёт второй ход; покрыто тестами `test_late_result_recoverable`
  и проверкой one-turn в direct-http. Клиентский таймаут настроен через конфигурацию.

### T5: машиночитаемые коды исхода и флаг повтора

- Агент пишет `nrel_ui_message_code` для каждого assistant-сообщения: pending →
  `pending`, успех → `ok`, ошибки → `llm_unavailable`, `llm_timeout`, `busy`,
  `invalid_request`, `cancelled`, `agent_restarted`, `internal`. Полный перечень,
  включая `schema_missing`, `schema_mismatch`, `dialog_not_found`, зафиксирован
  в `docs/01_CONTRACTS.md` и новом `contract/identifiers.json`.
- `AssistantMessage` получил обязательные `code` и `retryable`; transports
  читают код из БЗ/SSE, старые сообщения без link получают `ok`. `retryable`
  вычисляется из кода, редактор показывает «Повторить» только по флагу.
- `ScMemoryTransport.readMessage()` поддерживает отсутствующий relation code
  как обратную совместимость с прежней БЗ.
- Тесты: все коды из контракта, `llm_unavailable`/`llm_timeout`/`busy`/
  `agent_restarted`, код `ok` для успеха и SSE-события direct-http.

### T4: health из узла состояния сервиса и гейт показа чата

- `KnowledgeService.health()` принимает `ServiceState` и возвращает
  `schemaLoaded`, `agentAlive` (heartbeat свежее `service_lease_ttl_s`), `state`,
  `model`, `packVersion`, `promptVersion`, `knowledgeSource`, `queueDepth`,
  `contractVersion`; поля `llm`/`kb` сохранены для обратной совместимости.
  В узле состояния добавлено состояние `busy`.
- `ScMemoryTransport.health()` читает снимок из `nrel_ui_service_state` и не
  зависит от истории сообщений; fallback по истории остаётся только при
  недоступном узле. `DirectHttpTransport` передаёт новые поля в панель.
- `AssistantHealth` расширен новыми полями (опциональными) — миграции не требуется.
  Панель скрывает чат без схемы, а при неживом агенте показывает баннер и блокирует ввод.
- `docs/01_CONTRACTS.md`: правило для редактора; `docs/04_INTEGRATION.md`: пример gating.
- Тесты: `test_health_from_service_node`, протухший heartbeat/остановка агента,
  разбор снимка и проверка аренды в панели.

### T3: таймауты из конфигурации, клиент ждёт дольше LLM

- В `Settings` добавлен `dialog_client_timeout_s: float = 35.0` с валидатором:
  при `dialog_client_timeout_s <= llm_timeout_s` сервер падает при старте с
  понятным сообщением (`test_timeout_order_validation`).
- Клиентский таймаут убран из констант: `ACTION_TIMEOUT_MS = 30_000` удалён из
  `scMemory.ts`. `ScMemoryTransport` и `DirectHttpTransport` получают
  `clientTimeoutMs` из конструктора (по умолчанию из
  `import.meta.env.VITE_DIALOG_CLIENT_TIMEOUT_S`, fallback 35 000 мс).
- `LLM_TIMEOUT_S_BATCH` используется только в eval; в интерактиве — `LLM_TIMEOUT_S`.
- `/health` и отчёт eval показывают фактические `llm_timeout_s` и
  `dialog_client_timeout_s`.
- `.env.example`, `docs/04_INTEGRATION.md`, `docs/01_CONTRACTS.md`: согласованная
  тройка `LLM_TIMEOUT_S=25`, `DIALOG_CLIENT_TIMEOUT_S=35`,
  `VITE_DIALOG_CLIENT_TIMEOUT_S=35000`; правило «клиент ждёт дольше, чем
  генерирует LLM»; предупреждение про 30 с предпросмотра редактора.

### T2: диалог восстанавливается после F5 и не создаётся молча

- Контракт `AssistantTransport` изменён: `ensureDialog(dialogId?: string): Promise<string>`.
  Без id — создать новый диалог; с id — открыть существующий (`nrel_ui_id`);
  невалидный/ненайденный id — `DialogNotFoundError` (`dialog_not_found`), создание
  нового диалога не выполняется молча.
- `ask(dialogId, …)` больше не подменяет диалог: неизвестный id — типизированная
  ошибка `DialogNotFoundError`; ошибка уходит в UI как «диалог не найден».
- Сервис direct-http: добавлен `GET /dialog/{dialog_id}` (`exists`); `POST /ask`
  с неизвестным `dialog_id` отвечает `404 dialog_not_found`. Без `dialog_id` —
  как раньше, создаётся новый диалог.
- Панель: `AssistantPanel` при монтировании вызывает `transport.ensureDialog(dialogIdProp)`
  — с id редактора восстанавливает диалог, без id создаёт новый; история
  читается после успешного `ensureDialog`.
- Контракт и `docs/04_INTEGRATION.md` фиксируют разделение ответственности:
  id хранит редактор (`sessionStorage`, ключ `dialogId:<interfaceId>`), модуль —
  только БЗ; стартовая последовательность: `health()` → `ensureDialog(savedId)` →
  `history(savedId)`.

### T1: знания актуализированы под каталог редактора от 24.11.2026

**Причина смены ground truth:** в `ostis-ui-editor@6fbb2e6` (`4a791c1`)
`catalog.ts` исключил `action_id` у всех типов, кроме `button`, `select`,
`menu_item`; в `970b994` добавлены `nrel_ui_input_target` /
`nrel_ui_output_target`. Прежнее правило «набор из 27 свойств одинаков у всех
типов» и few-shot про divider/action_id учили неверному. Проверки и эталоны
меняются вслед за кодом, а не под ответ модели.

- `EXISTING_RELATIONS` дополнены `nrel_ui_input_target` и
  `nrel_ui_output_target`; в pack теперь 6 отношений с источниками и целями.
- В pack добавлен per-type `allowed_props` из `catalog.ts`; в текстах типов
  явно указано `свойств: 27 (с action_id)` или `26 (без action_id)`.
- Промпт `v4`: правило 5 заменено на «набор свойств зависит от типа;
  `action_id` только у трёх источников действий»; правило 6 описывает
  `input_target`/`output_target`; few-shot переписаны и дополнены примерами
  допустимой и недопустимой связи.
- Русские подписи типов берутся из i18n редактора (`type.<typeId>`); источник
  зафиксирован в `provenance.json` (`catalog_labels`).
- Из `ENVIRONMENT_IDENTIFIERS` и текстов знаний удалены
  `nrel_html_template`, `nrel_html_parameter_id`, `nrel_sc_template`,
  `rrel_specific_realisation`; остались `action_translate_sc_to_html`,
  `concept_current_ostis_ui_model`, `nrel_html_representation`.
- Добавлен `tools/check_upstream_drift.py` и `make drift`; проверка входит в
  `make test`, сравнивает код редактора/транслятора с pack и пинами, а
  расхождение `docs/catalog.md` выводит отдельным WARN.
- Пины `external/` обновлены: `ostis-ui-editor@6fbb2e6`,
  `ostis-ui@cff70b1`; pack и `ui_catalog_knowledge.scs` пересобраны.
- Знания сжаты, чтобы блок ЗНАНИЙ остался в бюджете 3500 токенов (3497).
- Добавлены тесты `test_action_id_only_for_action_sources`,
  `test_no_stale_environment_identifiers`, проверки отношений и few-shot.
- Хэш `prompt_v4.md` в `eval/frozen.json` обновлён до прогонов; gold/holdout
  не менялись. Пересмотр `q003`/`q014` и новая заморозка — в T12.
