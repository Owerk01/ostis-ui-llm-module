# Changelog

## Unreleased

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
