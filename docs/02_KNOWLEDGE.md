# 02. Знания

Статус: черновик M1. Полная инструкция «с нуля» заполняется в M4-T3.

## Источники

| Что | Откуда | Коммит |
|---|---|---|
| Типы, свойства, значения по умолчанию | `external/ostis-ui-editor` (`docs/catalog.md`, `client/src/model/catalog.ts`, `client/src/model/propSets.ts`, `client/src/sc/names.ts`) | `f6eb4fa` |
| Формальная схема UI | `external/ostis-ui-editor/docs/abstract_ui_model.scs` | `f6eb4fa` |
| HTML-представление (справка) | `external/ostis-ui` | `a673766` |
| A/B/C-адаптация (справка) | `external/UI-adaptation` | `5c3d627` |

Фактические коммиты — [`../knowledge/provenance.json`](../knowledge/provenance.json).

## Knowledge pack (M1)

`knowledge/pack.json` — нормализованная выжимка каталога, которая целиком
подаётся в системный промпт. RAG и эмбеддингов нет: при `num_ctx=8192` блок
знаний занимает ~2570 токенов (оценка `len/3`), системный промпт — ~3113.

Состав:

- `component_types` — 16 типов: `type_id`, `sc_class`, `label_ru`, `purpose_ru`,
  `defaults` (полный набор свойств из `catalog.ts`);
- `properties` — 27 свойств: `key`, `sc_class`, `type`, `default`, допустимые
  значения, `meaning_ru`;
- `relations` — 4 отношения: `nrel_ui_contains`, `nrel_ui_has_component`,
  `nrel_ui_id`, `nrel_ui_value`;
- `principles`, `methodology_stages`, `environment_notes` — пусты в M1,
  заполняются в M2-T2 из текстов проекта через БЗ.

Русские назначения и смыслы хранятся отдельно в
`knowledge/purpose_overrides.json`, чтобы не теряться при пересборке:
`catalog.ts` даёт только машинные defaults и ярлыки.

### Пересборка

```bash
make pack
# или напрямую:
python tools/build_knowledge_pack.py
```

Основной путь:

1. `tools/dump_catalog.ts` через `npx --yes tsx` импортирует исходники
   редактора **только для чтения** и печатает точный JSON;
2. `tools/build_knowledge_pack.py` добавляет русские тексты из
   `purpose_overrides.json`;
3. обновляются `knowledge/pack.json` и `knowledge/provenance.json`
   (`repo@commit:file`, `extracted_at`, `degraded`).

Резервный путь (`--no-npx` или ошибка Node): разбор `docs/catalog.md`.
В этом режиме per-type `defaults` пусты, `degraded = true`, сервис пишет WARN.
Такой pack годится для ответов о типах и свойствах, но не о размерах по
умолчанию.

### Когда менять

| Событие | Действие |
|---|---|
| Георгий изменил `catalog.ts`/`names.ts` | `make pack`, прогнать `make test`, при необходимости обновить `purpose_overrides.json` |
| Добавился тип или свойство | проверить, что идентификатор есть в разделе 3.6 AGENTS.md; иначе — остановиться и согласовать |
| Изменились defaults | пересобрать pack; тест `test_pack.py` проверит типы значений |
| Коммит external обновился | `provenance.json` обновится сам; зафиксировать новый хеш в PROGRESS |

## Сборка БЗ в M0/M1

`platform/repo.path` ссылается на external-файлы напрямую; пути разрешаются
относительно каталога `platform/`, поэтому используются `../external/...`.
Сборка: `make kb` → `.runtime/kb.bin` (~3 мин). Пересборка требует остановленной
sc-machine: `make kb` проверяет pid и отказывается перезаписывать открытую БЗ.
Наши знания (`kb/ui_assistant/`) добавляются в repo.path в M2-T5.

## M1: откуда берутся ответы

- Сервис читает `knowledge/pack.json` при старте.
- `/health.knowledge_source` в M1 всегда `fallback`, потому что чтение из
  sc-памяти появится в M2-T6. Это честная деградация, а не ошибка.
- Панель показывает баннер «Знания загружены из локальной копии, БЗ недоступна».
- `pack_version` — ISO-время сборки; он попадает в журнал и в событие `done`.

## M2: что добавится

1. `kb/ui_assistant/*.scs` — принципы, методика, устройство среды.
2. `kb/ui_assistant/generated/ui_catalog_knowledge.scs` — навешивание
   `nrel_ui_knowledge_text`/`nrel_ui_knowledge_source` на существующие классы
   (без объявления чужих узлов).
3. `knowledge/kb_reader.py` — чтение знаний из sc-памяти с fallback на pack.
4. `/health.knowledge_source = kb`, `kb_partial` при неполных текстах.

## Проверка целостности

```bash
make test
```

Тесты `service/tests/test_pack.py` проверяют: 16/27/4, уникальность ключей,
соответствие `sc_class`, типы значений, наличие provenance, отсутствие
`degraded`. Тесты рендера — бюджет 3500 токенов и отсутствие незаполненных
плейсхолдеров.
