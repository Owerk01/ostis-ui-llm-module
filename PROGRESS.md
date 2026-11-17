# PROGRESS — журнал выполнения

Версия контракта: 1.0 (2026-11-17)
Текущая веха: **M0 — подготовка и смоук платформы (завершена)**

## Состояние вех

| Веха | Статус | Комментарий |
|---|---|---|
| M0 | **выполнена** | каркас, external, LLM, sc-machine, смоук — все DoD закрыты |
| M1 | не начата | локальная модель + сервис + панель |
| M2 | не начата | знания в БЗ + sc-агент |
| M3 | не начата | качество ответов и оценка |
| M4 | не начата | встраивание и документация |

## M0 — подготовка и смоук платформы

| Задача | Статус | Что сделано / чем проверено |
|---|---|---|
| M0-T1. Каркас репозитория | **выполнено** | Структура раздела 3.3, `.gitignore`, `Makefile`, `.env.example`, `PROGRESS.md`, каркас `docs/`, `kb/`, `service/`, `panel/`, `tools/`, `eval/`; git-репозиторий инициализирован |
| M0-T2. Клонирование external | **выполнено** | `ostis-ui-editor@f6eb4fa`, `ostis-ui@a673766` (ветка `feature/SCS_to_HTML`), `UI-adaptation@5c3d627`, дополнительно `ostis-example-app@48218b5` (0.10.0) для базовых онтологий; фактические хэши в `knowledge/provenance.json` |
| M0-T3. Ollama и модель | **выполнено** | Ollama 0.40.16 установлена пользовательски в `~/.local` (без sudo); `qwen3.5:4b` Q4_K_M, 4.2B, ctx 262144; сервер с `OLLAMA_CONTEXT_LENGTH=8192`, KV `q8_0`, FA=1, max_loaded=1, parallel=1; `ollama ps` → **100% GPU**, 3.2 GB, context 8192 |
| M0-T4. Три запроса к LLM | **выполнено** | `tools/llm_smoke_test.py`: три связных ответа на русском; метрики ниже |
| M0-T5. sc-machine и БЗ | **выполнено** | Нативный prebuilt sc-machine/sc-builder 0.10.5; БЗ собрана из `ostis-example-app/knowledge-base` + `abstract_ui_model.scs` + `ui_examples`; порт 8090 слушает; 96 123 элемента (23 661 узел, 56 822 дуги, 15 640 ссылок) |
| M0-T6. `kb_smoke_test.py` | **выполнено** | Подключение по ws, резолв `concept_ui_interface`, `nrel_ui_has_component`, `ex_login`; прочитано **12 компонентов**, у всех определён тип `concept_ui_*` |

## Проверки M0 (фактические результаты)

### Смоук БЗ (`make smoke`)

```
concept_ui_interface = ScAddr(66212)
nrel_ui_has_component = ScAddr(70844)
components: 12
  ex_login_cmp_1: concept_ui_window
  ex_login_cmp_2: concept_ui_image
  ex_login_cmp_3: concept_ui_text
  ex_login_cmp_4: concept_ui_text
  ex_login_cmp_5: concept_ui_text_field
  ex_login_cmp_6: concept_ui_text
  ex_login_cmp_7: concept_ui_text_field
  ex_login_cmp_8: concept_ui_text
  ex_login_cmp_9: concept_ui_divider
  ex_login_cmp_10: concept_ui_button
  ex_login_cmp_11: concept_ui_button
  ex_login_cmp_12: concept_ui_text
СМОУК ПРОЙДЕН
```

Проверено также, что в собранной БЗ резолвятся стандартные узлы `action`,
`action_initiated`, `action_finished`, `action_finished_successfully`,
`nrel_main_idtf`, `lang_ru`, `rrel_1`, `nrel_system_identifier` — базы достаточно
для контракта действия M2.

### LLM без системного промпта (M0-T4)

| № | Вопрос | Latency | Prompt tokens | Output tokens | tok/s |
|---|---|---|---|---|---|
| 1 | Типы компонентов ПИ в OSTIS | 136.69 с (холодный старт + загрузка весов) | 38 | 945 | 6.91 (с загрузкой) |
| 2 | Отличие button от menu_item | 13.98 с | 39 | 877 | 62.74 |
| 3 | Свойства компонента и `visible` | 15.24 с | 36 | 787 | 51.63 |

Ответы связные, на русском. Модель без промпта отвечает общими сведениями о
веб-UI (Material Design, HTML/CSS), а не о каталоге OSTIS — это подтверждает
необходимость knowledge pack и системного промпта в M1.

VRAM при загруженной модели: `nvidia-smi` → 3 989 MiB использовано из 8 151 MiB
(модель + KV-кэш), запас для coding-агента и панели достаточен.

### Время `make up`

- первый запуск (сборка БЗ + загрузка модели): вне лимита NFR-10, т.к. включает
  первичную сборку БЗ (~3 мин) и скачивание весов;
- повторный `make up` при наличии `.runtime/kb.bin` и модели: **< 1 с** (проверка
  сервисов), что укладывается в NFR-10;
- явная пересборка БЗ — `make kb` (~3 мин), требует остановленной sc-machine.

## Журнал решений и отклонений

- **2026-11-17. Установка Ollama без sudo.** Системного Ollama нет, `sudo` недоступен.
  Использован официальный архив `ollama-linux-amd64.tar.zst`, распакованный в
  `~/.local` (бинарник `~/.local/bin/ollama`, библиотеки `~/.local/lib/ollama`).
  Это не меняет контракт: сервис обращается к `LLM_BASE_URL`.
- **2026-11-17. sc-machine.** Используется официальный prebuilt-релиз 0.10.5
  (Linux, x86_64), а не сборка из исходников: Docker для запуска не требуется.
  Бинарники и `kb.bin` лежат в `.runtime/` (в git не попадают).
- **2026-11-17. Схема UI не копируется.** `platform/repo.path` ссылается на
  `external/ostis-ui-editor/docs/abstract_ui_model.scs` и `ui_examples/` напрямую,
  как требует раздел 1.4. Каталог `knowledge-base/ui_editor_model/` из инструкции
  редактора эмулируется ссылкой в repo.path, без копирования файла.
- **2026-11-17. Пути repo.path.** sc-builder разрешает пути относительно каталога
  самого `repo.path`, поэтому в `platform/repo.path` используются `../external/...`.
- **2026-11-17. Направление дуги типа.** В SCs `component <- concept_ui_button;;`
  создаёт дугу **от класса к компоненту**; смоук ищет тип шаблоном
  `(VAR_NODE_CLASS) --VAR_PERM_POS_ARC--> (component)`. Это учтено на будущее
  для `kb_reader.py`.
- **2026-11-17. Защита БЗ.** `make kb` отказывается работать при запущенной
  sc-machine (она держит `.runtime/kb.bin` открытым); `make up` пересобирает БЗ
  только если её ещё нет.

## Совместимость платформы (снимает часть риска M2)

`py-sc-client 0.4.0` + `py-sc-kpm 0.4.0` успешно работают с `sc-machine 0.10.5`:
подключение, `ScKeynodes.resolve`, `search_by_template`, чтение 12 компонентов.
Блокирующий риск M0 не подтвердился. Версию платформы всё равно нужно
согласовать с командой (раздел 7 AGENTS.md).

## Блокеры

- нет
