# 02. Знания

Знания читаются из sc-памяти; локальный pack остаётся резервной копией.
Процедуры пересборки воспроизводимы с нуля.

## Источники

| Что | Откуда | Коммит |
|---|---|---|
| Типы, свойства, связи, значения по умолчанию | `external/ostis-ui-editor` (`client/src/model/catalog.ts`, `client/src/model/linkRules.ts`, `client/src/model/propSets.ts`, `client/src/model/types.ts`, `client/src/sc/names.ts`, `client/src/i18n/ru.ts`) | `6fbb2e6` |
| Формальная схема UI | `external/ostis-ui-editor/docs/abstract_ui_model.scs` | `6fbb2e6` |
| HTML-представление (справка) | `external/ostis-ui` | `cff70b1` |
| A/B/C-адаптация (справка) | `external/UI-adaptation` | `5c3d627` |

Фактические коммиты — [`../knowledge/provenance.json`](../knowledge/provenance.json).

## Knowledge pack

`knowledge/pack.json` — нормализованная выжимка каталога и домен-знаний,
которая целиком подаётся в системный промпт. RAG и эмбеддингов нет: при
`num_ctx=8192` блок знаний занимает **3497 токенов** (оценка `len/3`), системный
промпт вместе с few-shot — около 5260 токенов (оценка). Это верхняя
граница бюджета 3500; при её превышении `render.py` усекает
`methodology_stages` и `environment_notes` до заголовков и пишет WARN.

Состав:

- `component_types` — 16 типов: `type_id`, `sc_class`, `label_ru`, `purpose_ru`,
  `allowed_props` (из `catalog.ts`), `defaults` (полный набор свойств);
- `properties` — 27 свойств: `key`, `sc_class`, `type`, `default`, допустимые
  значения, `meaning_ru`;
- `relations` — 6 отношений: `nrel_ui_contains`, `nrel_ui_input_target`,
  `nrel_ui_output_target`, `nrel_ui_has_component`, `nrel_ui_id`,
  `nrel_ui_value`; у связей действий указаны источники и цели;
- `link_rules` — наборы `action_sources`, `input_targets`, `output_targets`
  из `linkRules.ts`;
- `principles` — 5 принципов;
- `methodology_stages` — 1 узел «процессы методики» + 10 этапов;
- `environment_notes` — 5 сведений об устройстве среды.

Русские тексты принципов, методики и среды живут в `kb/ui_assistant/*.scs`.
`build_knowledge_pack.py` парсит их в pack, чтобы режимы `kb` и `fallback`
давали одинаковый промпт и не расходились.

Русские назначения и смыслы хранятся отдельно в
`knowledge/purpose_overrides.json`, чтобы не теряться при пересборке:
`catalog.ts` даёт машинные defaults и `allowed_props`, подписи типов — из
`client/src/i18n/ru.ts` (`type.<typeId>`).

`render.py` добавляет в начало перечислений строки `типов: 16`,
`свойств: 27; …`, `отношений: 6`, `принципов: 5`. Они убирают
пропуски последнего элемента в ответах «перечисли все». Рабочий шаблон —
`knowledge/prompt_v4.md`; он закреплён в `Settings.prompt_path` и `.env.example`
(`PROMPT_VERSION=v4`).

Методика рендерится **сгруппированно**: заметка `ui_methodology_processes` идёт
отдельной записью, затем три заголовка вида `процесс: … | этапов: N` и этапы
каждого процесса. Принадлежность этапа выводится детерминированно из префикса
idtf (`ui_stage_initial_*`, `ui_stage_editing_*`, `ui_stage_adaptation_*`) и
хранится в поле `process` pack-файла. Это убирает путаницу этапов между процессами.

В `purpose_overrides.json` уточнены назначения, где модель ошибалась: у slider
границы диапазона каталогом не заданы (`min_width`/`max_width` — размер), у
divider прямо указано, что `action_id` ему недоступен. Ограничение `action_id`
(только `button`, `select`, `menu_item`) приходит из `allowed_props` каталога,
а не задаётся вручную. Заметка об HTML-представлении компонентов в
`ui_environment.scs` содержит только актуальный `nrel_html_representation`.

Бюджет блока ЗНАНИЙ — ровно **3500 токенов**: новые тексты сжаты так, чтобы
усечение methodology/environment не срабатывало. Тест `test_knowledge_fits_budget`
проверяет это.

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
| Изменился `catalog.ts`/`linkRules.ts`/`names.ts`/`types.ts`/i18n в редакторе | `make pack`, затем `make drift`; `make test` запускает drift автоматически |
| Добавился тип, свойство или связь | проверить, что идентификатор есть в зафиксированном контракте `service/src/ostis_ui_assistant/knowledge/identifiers.py`; иначе — согласовать имя с командой |
| Изменились defaults или `allowed_props` | пересобрать pack; `test_pack.py` проверит типы значений и ограничение `action_id` |
| Коммит external обновился | `make pack` обновит `provenance.json`; `make drift` сверит пины с рабочими копиями |

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
| `kb/ui_assistant/ui_dialog.scs` | классы диалога, знаний, 12 `nrel_ui_*`, класс действия |
| `kb/ui_assistant/ui_principles.scs` | 5 принципов с текстом и provenance |
| `kb/ui_assistant/ui_methodology.scs` | процесс методики + 10 этапов |
| `kb/ui_assistant/ui_environment.scs` | 5 сведений об устройстве среды |
| `kb/ui_assistant/generated/ui_catalog_knowledge.scs` | 16+27+6 текстов на существующих классах и отношениях |

Сгенерированный файл **ничего не объявляет**: только
`=> nrel_ui_knowledge_text` и `=> nrel_ui_knowledge_source` на классах и
отношениях редактора. Это проверяет `tools/check_id_collisions.py` и тест
`test_generated_scs_attaches_without_declaring`.

## Откуда берутся ответы

- При `KNOWLEDGE_SOURCE=kb` сервис при старте читает:
  - тексты 16 типов и 27 свойств — `nrel_ui_knowledge_text` у классов
    `concept_ui_*`;
  - тексты 6 отношений — `nrel_ui_knowledge_text` у узлов `nrel_ui_*`;
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

## Воспроизводимость с нуля

Порядок на чистой машине (Linux x86_64; для Windows — WSL2, см. README):

```bash
# 1. Источники истины — только для чтения, фиксируем коммиты из provenance.json
mkdir -p external
git clone https://github.com/vodo4kin/ostis-ui-editor external/ostis-ui-editor
git -C external/ostis-ui-editor checkout 6fbb2e6
git clone -b feature/SCS_to_HTML https://github.com/Glentas/ostis-ui external/ostis-ui
git -C external/ostis-ui checkout cff70b1
git clone https://github.com/Oddchew/UI-adaptation external/UI-adaptation
git -C external/UI-adaptation checkout 5c3d627
git clone -b 0.10.0 https://github.com/ostis-apps/ostis-example-app external/ostis-example-app

# 2. Окружение и платформа
make venv
make setup                 # официальный prebuilt sc-machine 0.10.5
make ollama && make pull

# 3. Знания
make pack                  # pack.json + provenance + generated .scs + проверка коллизий
make machine-stop          # БЗ пересобирается только при остановленной sc-machine
make kb-load               # build_kb → machine → smoke

# 4. Проверки
make test
make eval ARGS="--label clean-machine"
```

`external/` в `.gitignore`: клоны не попадают в репозиторий, но обязательны для
`make pack` и `make kb-load`. Если Node недоступен, `build_knowledge_pack.py`
откатывается к разбору `docs/catalog.md` и ставит `degraded = true` — сервис
пишет WARN, а ответы о размерах по умолчанию будут недоступны.

## Проверка целостности

```bash
make test
```

Тесты `service/tests/test_pack.py` проверяют: 16/27/4, уникальность ключей,
соответствие `sc_class`, типы значений, наличие provenance, отсутствие
`degraded`. Тесты рендера — бюджет 3500 токенов и отсутствие незаполненных
плейсхолдеров.
