# PROGRESS — журнал правок по FIXES.md

## FIX-P0-1. Read-путь не создаёт узлы в БЗ

Изменено:

- `knowledge/kb_reader.py`: `_class_text` использует `ScKeynodes.get()` вместо
  `ScKeynodes.resolve(..., CONST_NODE_CLASS)`; отсутствующий класс даёт `None`
  и штатный per-item fallback.
- `agents/dialog_agent.py`: `_source_addrs` использует `ScKeynodes.get()`,
  префикс `concept_ui_` применяется только к ключам свойств (`PROPERTY_KEYS`);
  невалидные адреса больше не попадают в основания.
- `panel/src/transport/scMemory.ts`: `resolveKeynodes` получает невалидный тип
  `new ScType()` (поиск без создания); отсутствующие keynodes → ошибка
  «Схема ассистента не загружена в БЗ. Выполните make kb-load», `health.connected=false`.
- Добавлены `platform/repo.path.assistant-only`, цель `make kb-load-noschema`,
  env-оверрайды `KB_OUTPUT` / `KB_REPO_PATH` / `SC_STORAGE` / `SC_PID_FILE`
  в скриптах сборки и запуска sc-machine.
- Новые тесты: `test_read_path_never_resolves_with_type` ( статический,
  пакет `sc/` исключён намеренно) и `test_no_foreign_nodes_created`
  (маркер `kb_noschema`).
- `docs/01_CONTRACTS.md`: красная линия переформулирована как «read-путь не пишет».

До исправления — статический тест:

```
FAILED service/tests/test_read_path.py::test_read_path_never_resolves_with_type
  knowledge/kb_reader.py:86: ScKeynodes.resolve(sc_class, sc_type.CONST_NODE_CLASS)
  agents/dialog_agent.py:108: ScKeynodes.resolve(idtf, sc_type.UNKNOWN)
  agents/dialog_agent.py:110: ScKeynodes.resolve(f"concept_ui_{idtf}", sc_type.UNKNOWN)
1 failed
```

До исправления — интеграционный тест на БЗ без схемы:

```
FAILED service/tests/test_kb_noschema.py::test_no_foreign_nodes_created
  assert not ScKeynodes.get("concept_ui_button").is_valid()
1 failed
```

После исправления:

```
service/tests/test_read_path.py .................................. 1 passed
RUN_NOSCHEMA_TEST=1 pytest -m kb_noschema ... 1 passed
panel npm run typecheck: ok
```

## FIX-P0-2. Таймер обработки показывает правдоподобное время

Изменено:

- `panel/src/AssistantPanel.tsx`: `startedAt` и `now` обе в базе `performance.now()`;
  интервал 100 мс живёт, пока `pendingId !== null`, и очищается при завершении,
  отмене и размонтировании; при старте запроса обе величины обновляются одним
  значением; `elapsedMs` ограничен снизу нулём.
- Новая функция `panel/src/utils/formatElapsed.ts`: отсекает отрицательные
  значения и значения больше таймаута транспорта (180 с).
- `StatusBar` использует общую функцию; `tools/e2e_panel.py` проверяет таймер
  через 1 с после отправки и использует `127.0.0.1:5173`.
- Unit-тест `panel/src/utils/formatElapsed.test.ts` (node:test, без новых зависимостей),
  цель `npm test` включена в `make test`.

До исправления — e2e:

```
E2E_MODE=sc-memory python tools/e2e_panel.py
AssertionError: таймер показывает '1795024152,9 с'
```

До исправления — unit-тест:

```
Error [ERR_MODULE_NOT_FOUND]: Cannot find module .../formatElapsed.ts
# fail 1
```

После исправления:

```
npm test: 2 passed, 0 failed
e2e: indicator_ms=86; timer: 1,0 с; cancel: сообщение помечено «Отменено»
screenshot: docs/screenshots/m2-panel-sc.png
```

## FIX-P0-3. Фактические ошибки и недостоверная оценка

Изменено:

- `tools/build_knowledge_pack.py`: этапы методики получают поле `process`
  (`initial` / `editing` / `adaptation`) из idtf; заметка о процессах остаётся
  отдельной записью; provenance дополнена источником HTML-транслятора.
- `render.py`: методика рендерится с заголовками процессов и счётчиками этапов;
  добавлены few-shot про divider/action_id, этапы адаптации, slider, этапы
  начальной разработки, interaction через БЗ и отказ для видеоплеера.
- `knowledge/prompt_v4.md`: убрана клаузула «завершающие этапы», добавлены
  запреты переносить этапы между процессами, называть idtf разделами документа,
  предлагать замену при отказе, окончательные проверки перед ответом; v3 сохранён.
- `purpose_overrides.json` и `ui_methodology.scs`/`ui_environment.scs`: уточнены
  slider/divider/sound, сжаты тексты, добавлена заметка об HTML-представлении.
  Бюджет ЗНАНИЙ — ровно 3500 токенов, усечение не срабатывает.
- Минимальный P1-1: `ENVIRONMENT_IDENTIFIERS` в whitelist; жёсткий guard заменён
  на санитизацию + вызов LLM; детерминированный отказ только при пустом остатке.
- Оценка: `tools/run_eval.py` получил `--cold`, хэши выборок/промпта, `tainted`,
  `unknown_id_in_final_rate`, `injection_resistance`, `guard_sanitized_rate`,
  word-boundary проверку ключей свойств. Добавлены `eval/holdout_questions.jsonl`
  (29 вопросов, 5 инъекций), `eval/frozen.json`, `eval/manual_review.jsonl`
  (75 разметок). Проверки dev усилены по Приложению B.
- Документы: `docs/01_CONTRACTS.md` (определения метрик, ENVIRONMENT_IDENTIFIERS),
  `docs/02_KNOWLEDGE.md` (группировка методики), `docs/03_EVAL.md` (честные
  результаты), README (убрано «Accuracy 100%»).

До исправления — `test_methodology_grouped_with_counts`:

```
AssertionError: assert 'процесс: начальная разработка | этапов: 3' in 'ui_methodology_processes | ...'
1 failed
```

После исправления:

```
make test: 56 passed, 1 skipped, 3 deselected; npm typecheck + тест таймера — ok
knowledge_tokens 3500, truncated []
dev warm: accuracy 93.5%, refusal 100%, p95 1437 мс
dev cold: accuracy 93.5%, p95 5980 мс
holdout (1 прогон): accuracy 86.2%, refusal 66.7%, p95 1295 мс
factual_accuracy 71/75 = 0.947; incorrect_count = 2
```

Честно не выполнено: `incorrect_count = 0` (ошибки `q003`, `q022`) и отказы на
holdout 66.7% < 90%. Улучшение ответов возможно только через промпт и знания;
проверки holdout и пороги не менялись после прогона. Дальнейшее улучшение
ответов требует отдельной итерации промпта с новым зафиксированным прогоном holdout.
