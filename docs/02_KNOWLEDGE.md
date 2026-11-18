# 02. Знания

Статус: M2 — знания читаются из БЗ, pack остаётся локальным fallback.

## Источники

| Что | Откуда | Коммит |
|---|---|---|
| Типы, свойства, значения по умолчанию | `external/ostis-ui-editor` (`docs/catalog.md`, `client/src/model/catalog.ts`, `client/src/model/propSets.ts`, `client/src/sc/names.ts`) | `f6eb4fa` |
| Формальная схема UI | `external/ostis-ui-editor/docs/abstract_ui_model.scs` | `f6eb4fa` |
| HTML-представление (справка) | `external/ostis-ui` | `a673766` |
| A/B/C-адаптация (справка) | `external/UI-adaptation` | `5c3d627` |

Фактические коммиты — [`../knowledge/provenance.json`](../knowledge/provenance.json).

## Knowledge pack (M1)

`knowledge/pack.json` — нормализованная выжимка каталога и домен-знаний,
которая целиком подаётся в системный промпт. RAG и эмбеддингов нет: при
`num_ctx=8192` блок знаний занимает **3494 токена** (оценка `len/3`), системный
промпт — ~4021. Это верхняя граница бюджета 3500; при её превышении
`render.py` усекает `methodology_stages` и `environment_notes` до заголовков
и пишет WARN.

Состав:

- `component_types` — 16 типов: `type_id`, `sc_class`, `label_ru`, `purpose_ru`,
  `defaults` (полный набор свойств из `catalog.ts`);
- `properties` — 27 свойств: `key`, `sc_class`, `type`, `default`, допустимые
  значения, `meaning_ru`;
- `relations` — 4 отношения: `nrel_ui_contains`, `nrel_ui_has_component`,
  `nrel_ui_id`, `nrel_ui_value`;
- `principles` — 5 принципов (§5 проекта);
- `methodology_stages` — 1 узел «процессы методики» + 10 этапов (§4);
- `environment_notes` — 4 сведения об устройстве среды (§7).

Русские тексты принципов/методики/среды живут в `kb/ui_assistant/*.scs`.
`build_knowledge_pack.py` парсит их в pack, чтобы режимы `kb` и `fallback`
давали одинаковый промпт и не расходились.

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

## Сборка БЗ

`platform/repo.path` ссылается на external-файлы и наш фрагмент напрямую;
пути разрешаются относительно каталога `platform/`, поэтому используются
`../external/...` и `../kb/ui_assistant`.

Сборка: `make kb` → `.runtime/kb.bin` (~3 мин). Пересборка требует остановленной
sc-machine: `make kb` проверяет pid и отказывается перезаписывать открытую БЗ.
Явная цель с перезапуском и смоуком — `make kb-load`.

### Файлы нашего фрагмента

| Файл | Содержимое |
|---|---|
| `kb/ui_assistant/ui_dialog.scs` | классы диалога, знаний, 9 `nrel_ui_*`, класс действия |
| `kb/ui_assistant/ui_principles.scs` | 5 принципов с текстом и provenance |
| `kb/ui_assistant/ui_methodology.scs` | процесс методики + 10 этапов |
| `kb/ui_assistant/ui_environment.scs` | 4 сведения об устройстве среды |
| `kb/ui_assistant/generated/ui_catalog_knowledge.scs` | 16+27 текстов на существующих классах |

Сгенерированный файл **ничего не объявляет**: только
`=> nrel_ui_knowledge_text` и `=> nrel_ui_knowledge_source` на классах
редактора. Это проверяет `tools/check_id_collisions.py` и тест
`test_generated_scs_attaches_without_declaring`.

## Откуда берутся ответы (M2)

- При `KNOWLEDGE_SOURCE=kb` сервис при старте читает:
  - тексты 16 типов и 27 свойств — `nrel_ui_knowledge_text` у классов
    `concept_ui_*`;
  - принципы — экземпляры `concept_ui_development_principle`;
  - методику — `concept_ui_knowledge` (процессы) + `concept_ui_development_stage`;
  - среду — `concept_ui_environment_note`.
- Если у отдельного класса текста нет, берётся запись из `pack.json`, а в
  `/health` выставляется `kb.partial = true` и список `kb.missing`.
- Если sc-память недоступна, сервис работает на `pack.json`
  (`knowledge_source = fallback`), панель показывает «Знания из локальной копии».
- `pack_version` — ISO-время сборки; он попадает в журнал, в
  `nrel_ui_prompt_version` сообщения и в событие `done`.

## Обновление знаний

1. Правки текстов — в `kb/ui_assistant/*.scs` (одна строка в `[...]`, без
   переносов). После правки: `make pack` → `make kb-load`.
2. Правки каталога приходят из `external/ostis-ui-editor`. После обновления
   коммита: `make pack` (pack + generated `.scs` + проверка коллизий) →
   `make kb-load` → `make test`.
3. Если в БЗ нет текста для класса, сервис не падает: он берёт pack и честно
   помечает частичную деградацию. Проверка: `curl /health | jq .kb`.

## Проверка целостности

```bash
make test
```

Тесты `service/tests/test_pack.py` проверяют: 16/27/4, уникальность ключей,
соответствие `sc_class`, типы значений, наличие provenance, отсутствие
`degraded`. Тесты рендера — бюджет 3500 токенов и отсутствие незаполненных
плейсхолдеров.
