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
