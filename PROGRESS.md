# PROGRESS — журнал выполнения

Версия контракта: 1.0 (2026-11-17)
Текущая веха: **M1 — локальная модель, сервис и панель (завершена)**

## Состояние вех

| Веха | Статус | Комментарий |
|---|---|---|
| M0 | **выполнена** | каркас, external, LLM, sc-machine, смоук — все DoD закрыты |
| M1 | **выполнена** | pack 16/27/4, два LLM-бэкенда, валидатор, FastAPI/SSE, панель, прогон 12 вопросов |
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

## M1 — локальная модель, сервис и панель

| Задача | Статус | Что сделано / чем проверено |
|---|---|---|
| M1-T1. Конфигурация и LLM-бэкенды | **выполнено** | `config.py` (pydantic-settings, `.env`), `llm/base.py` (Protocol + ошибки + статистика), `ollama_backend.py` (`/api/chat`, стрим, `think:false`, `num_ctx`, `keep_alive`), `openai_backend.py` (SDK, стрим, предупреждение об игнорируемых Ollama-опциях). Оба бэкенда проходят общий контрактный тест на mock-клиентах, плюс 3 живых теста на Ollama |
| M1-T2. Knowledge pack | **выполнено** | `tools/dump_catalog.ts` импортирует `catalog.ts`/`propSets.ts`/`names.ts`; `build_knowledge_pack.py` собрал **16 типов, 27 свойств, 4 отношения**, `degraded=false`; русские тексты — в `purpose_overrides.json`; provenance обновлён (`ostis-ui-editor@f6eb4fa`) |
| M1-T3. Рендер и бюджет | **выполнено** | `knowledge/prompt_v1.md`, `knowledge/render.py`: компактный рендер «одна сущность — одна строка», 2 few-shot пары. Блок знаний **2570 токенов**, системный промпт **3113** при бюджете 3500; при превышении — усечение methodology/environment с WARN |
| M1-T4. Валидатор | **выполнено** | `knowledge/validate.py`: поиск `concept_/nrel_/rrel_/action_`, кириллица и регистр, один repair-запрос, вырезание остатка с пометкой, журналирование. Белый список включает ключи свойств (иначе `action_id` ложно считался галлюцинацией) |
| M1-T5. FastAPI | **выполнено** | `GET /health`, `POST /dialog`, `POST /ask` (SSE: `meta`/`delta`/`done`/`cancelled`/`error`), `GET /history/{id}`, `POST /cancel`; CORS для dev-стенда; lifespan вместо deprecated `on_event` |
| M1-T6. Панель | **выполнено** | `AssistantPanel` + `MessageList`, `Composer`, `StatusBar`, `SourceChips`, `EmptyState`; CSS-модули `oaa-*`, без глобальных селекторов; `DirectHttpTransport` с SSE и отменой; dev-стенд с переключателем транспорта и `onSourceClick`; `panel/README.md` |
| M1-T7. Ручной прогон | **выполнено** | 12 вопросов через `KnowledgeService`; e2e в headless Chrome: индикация 79 мс, чипы кликабельны, негативный вопрос, отмена |

### Контрактные и юнит-тесты

```
$ .venv/bin/pytest -q service/tests
45 passed, 3 deselected in 1.09s

$ .venv/bin/pytest -q service/tests/test_live_llm.py -m llm
3 passed in 2.99s
```

Покрыто: 16/27/4 и provenance pack; типы значений свойств; рендер и бюджет;
few-shot; выдуманные идентификаторы, кириллица, регистр, repair, вырезание;
контракт Ollama/OpenAI (payload, стрим, статистика, ошибки, health);
SSE-события, история, пустой вопрос, ошибки LLM/таймаут/отмена, `/cancel`.

### E2E панели

Сценарий `tools/e2e_panel.py` (headless Chrome, сервис + Vite):

```
health: статус fallback отображается
indicator_ms=79
answer: ответ про action_id получен, чипы оснований кликабельны
screenshot: docs/screenshots/m1-panel.png
negative: отказ вместо выдумки получен
cancel: сообщение помечено «Отменено»
console: ошибок нет
```

Скриншот: [`docs/screenshots/m1-panel.png`](docs/screenshots/m1-panel.png).

### Прогон 12 вопросов (M1-T7)

Профиль A: `qwen3.5:4b`, `100% GPU`, ctx 8192. Знания — `pack.json`.

| № | Категория | Latency, мс | Итог |
|---|---|---|---|
| 1 | catalog_type | 2809 | перечислил 16 типов |
| 2 | catalog_type | 2638 | отличие spacer/divider верное |
| 3 | catalog_type | 967 | select выбран верно |
| 4 | catalog_prop | 1287 | action_id + button/menu_item |
| 5 | catalog_prop | 985 | corner_radius=0, font_size=13 |
| 6 | catalog_prop | 1521 | text_field/text_area верно |
| 7 | compare | 1317 | contains vs has_component верно |
| 8 | catalog_prop | 1187 | отказ: «нет сведений» (см. ниже) |
| 9 | principle | 1006 | отказ (принципов ещё нет в pack) |
| 10 | methodology | 1066 | отказ (методики ещё нет в pack) |
| 11 | negative | 1227 | отказ вместо выдумки |
| 12 | out_of_scope | 1480 | перенаправил в редактор |

Итого: **p50 = 1257 мс, p95 = 2638 мс, max = 2809 мс**,
`hallucinated = 0`, вырезанных идентификаторов — 0. Первый `delta` приходит
после полной генерации, то есть ≤ 3 с на этом профиле.

Выводы для M3:

- вопросы 9–10 — ожидаемые отказы: тексты принципов и методики появятся в
  БЗ/pack в M2-T2, после чего ответы должны стать положительными;
- вопрос 8 («где хранится значение свойства») модель не вывела из смысла
  `nrel_ui_value`, хотя в pack написано «значение хранится в sc-link» —
  кандидат на переформулировку рендера свойств/отношений;
- отказы и out-of-scope ведут себя корректно, галлюцинаций нет;
- p95 с большим запасом укладывается в 20 с (NFR-2).

### Проверки M1

- `npm run build` панели: `tsc --noEmit && vite build` — успешно, 242.81 kB JS.
- `make test`: pytest + typecheck панели.
- `/health`: `knowledge_source=fallback`, `pack_version`, `prompt_estimated_tokens=3113`,
  `knowledge_estimated_tokens=2570`, модель `reachable=true`, `model_available=true`.
- Реальный SSE через curl: `meta` → 4+ `delta` → `done`, ответ с `action_id`.
- Отмена: панель помечает «Отменено», сервис выставляет событие и не пишет
  ошибочный ответ.



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
- **2026-11-17. M1: знания только из pack.** В M1 `effective_knowledge_source`
  всегда `fallback`, потому что чтения из sc-памяти ещё нет. `/health` и баннер
  панели показывают это честно; `kb` появится в M2-T6.
- **2026-11-17. M1: ответ буферизуется.** Сначала полная генерация и валидация,
  затем SSE-куски. Это осознанный компромисс: FR-13 (ноль выдуманных
  идентификаторов) важнее потоковости первого токена. Задержка первого `delta`
  на профиле A — 1–3 с.
- **2026-11-17. M1: отмена direct-http.** Панель передаёт локальный id, транспорт
  сам сопоставляет его с серверным `message_id` из `meta`. Контракт
  `AssistantTransport` не расширялся.
- **2026-11-17. M1: `action_id` — не галлюцинация.** Ключ свойства совпадает с
  префиксом `action_*`; белый список валидатора расширен `PROPERTY_KEYS`.
  Исправлено после живого прогона, покрыто тестом.
- **2026-11-17. M1: два исправленных дефекта.** `fetch`, сохранённый как поле
  класса, терял `this` (`Illegal invocation`) — добавлен `bind(globalThis)`.
  `uvicorn.run("ostis_ui_assistant.main:app")` повторно импортировал модуль и
  создавал второй `KnowledgeService` — теперь передаётся объект `app`.
- **2026-11-17. M1: e2e-скрипт вне зависимостей.** `tools/e2e_panel.py` требует
  `pip install playwright` и системный Chrome; в `make test` не входит, чтобы не
  утяжелять окружение. Скриншот `docs/screenshots/m1-panel.png` зафиксирован.

## Совместимость платформы (снимает часть риска M2)

`py-sc-client 0.4.0` + `py-sc-kpm 0.4.0` успешно работают с `sc-machine 0.10.5`:
подключение, `ScKeynodes.resolve`, `search_by_template`, чтение 12 компонентов.
Блокирующий риск M0 не подтвердился. Версию платформы всё равно нужно
согласовать с командой (раздел 7 AGENTS.md).

## Блокеры

- нет
