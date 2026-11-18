# PROGRESS — журнал выполнения

Версия контракта: 1.0 (2026-11-17)
Текущая веха: **M3 — качество ответов и оценка (завершена)**

## Состояние вех

| Веха | Статус | Комментарий |
|---|---|---|
| M0 | **выполнена** | каркас, external, LLM, sc-machine, смоук — все DoD закрыты |
| M1 | **выполнена** | pack 16/27/4, два LLM-бэкенда, валидатор, FastAPI/SSE, панель, прогон 12 вопросов |
| M2 | **выполнена** | 5 принципов, 10 этапов, 4 сведения, 43 текста каталога в БЗ; sc-агент; диалог и журнал в БЗ; транспорт `sc-memory` |
| M3 | **выполнена** | gold 46 вопросов; 3 версии промпта; A/B/C; acceptance-прогоны: accuracy 100%, hall. 0%, refusal 100% |
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



## M2 — знания в БЗ и sc-агент

| Задача | Статус | Что сделано / чем проверено |
|---|---|---|
| M2-T1. `ui_dialog.scs` | **выполнено** | Листинг 3.6: 9 классов, 9 `nrel_ui_*`, класс действия, `nrel_main_idtf` для диалога и действия. `kb/ui_assistant` подключён в `platform/repo.path` |
| M2-T2. Домен-знания | **выполнено** | `ui_principles.scs` — 5 принципов §5; `ui_methodology.scs` — процесс + 10 этапов §4; `ui_environment.scs` — 4 сведения §7. Тексты пишутся в `.scs`, `build_knowledge_pack.py` парсит их в pack, поэтому `kb` и `fallback` не расходятся |
| M2-T3. Generated `.scs` | **выполнено** | `tools/generate_kb_scs.py` → `kb/ui_assistant/generated/ui_catalog_knowledge.scs`: 16 типов + 27 свойств, только `nrel_ui_knowledge_text`/`nrel_ui_knowledge_source`, без объявлений типов |
| M2-T4. Коллизии | **выполнено** | `tools/check_id_collisions.py`: чужие классы/отношения не объявляются, набор объявленных совпадает с 3.6, тексты навешены только на классы из `abstract_ui_model.scs`; `test_kb_contract.py` (4 теста) |
| M2-T5. Загрузка в БЗ | **выполнено** | `make kb` (~3 мин) с `../kb/ui_assistant`; в БЗ 5 принципов, 10 этапов, 4 env-узла, 1 процесс, тексты 16+27; `nrel_ui_knowledge_text` у `concept_ui_button` читается |
| M2-T6. `kb_reader.py` | **выполнено** | Чтение текстов классов, принципов, этапов, env; per-item fallback на pack с `kb.partial`/`kb.missing`; `KnowledgeService` берёт источник из `KbStatus`. Live: `connected=True, source=kb, partial=False`, 16/27/5/11/4 |
| M2-T7. `dialog_store.py` | **выполнено** | Диалог, сообщение (роль, текст через `nrel_ui_value`, время, статус, модель, версия промпта, основания), нумерация `rrel_1..N`, чтение истории |
| M2-T8. sc-агент | **выполнено** | `agents/dialog_agent.py`, `agents/module.py`, dispatch в `main.py` по `ASSISTANT_TRANSPORT`. Действие из скрипта: `successfully`, ответ 270 символов, 1 основание, 1.5 с (после прогрева) |
| M2-T9. Транспорт панели | **выполнено** | `panel/src/transport/scMemory.ts`: создание действия, ожидание по событию/опросу, чтение истории, мягкая отмена; dev-переключатель транспорта и адреса sc-сервера; `StatusBar` показывает режим БЗ |
| M2-T10. Идемпотентность и ошибки | **выполнено** | Повторная доставка события → `SKIP`, сообщений 2 → 2; при остановленной Ollama действие `unsuccessfully`, сообщение `state=error` с понятным текстом |

### Бюджет промпта

| Блок | Токены (оценка `len/3`) |
|---|---|
| component_types | 1157 |
| properties | 1089 |
| relations | 153 |
| principles | 350 |
| methodology_stages | 539 |
| environment_notes | 217 |
| **итого** | **3494** (бюджет 3500, без усечения) |

Первая сборка домен-текстов дала 3505 токенов (перебор на 5): тексты принципов
и среды были сжаты, `purpose_ru` сокращены, `default_note_ru` для
`name`/`width`/`height` заменён на «зависит от типа».

### Проверки M2 (фактические результаты)

```
$ .venv/bin/pytest -q service/tests
49 passed, 3 deselected in 0.65s

$ .venv/bin/python tools/check_id_collisions.py
OK: 5 файлов .scs, 18 наших идентификаторов, коллизий нет

$ .venv/bin/python tools/action_smoke_test.py "Что такое concept_ui_button?"
status: successfully, elapsed_ms: 1533.9
sources: ["concept_ui_button"]
promptVersion: "v1|pack:2026-11-18T05:44:16Z"

$ E2E_MODE=sc-memory .venv/bin/python tools/e2e_panel.py
health: режим sc-memory, знания из БЗ
indicator_ms=86
answer: ответ про action_id получен, чипы оснований кликабельны
screenshot: docs/screenshots/m2-panel-sc.png
negative: отказ вместо выдумки получен
cancel: сообщение помечено «Отменено»
console: ошибок нет
```

Скриншот: [`docs/screenshots/m2-panel-sc.png`](docs/screenshots/m2-panel-sc.png).

### Дефект, найденный на M2-T9

Панель создавала ролевые связи `rrel_1`/`rrel_2` **common arc**
(`action --common--> значение`). `py-sc-kpm` ищет аргументы шаблоном
`action --VAR_PERM_POS_ARC--> значение`, поэтому агент видел пустой вопрос,
создавал новый диалог и завершал действие как `unsuccessfully`.
Исправлено: для `rrel_*` основная дуга теперь `ConstPermPosArc`; common arc
остаётся только для `nrel_*`. Проверено e2e в боевом режиме и тестом
`action_smoke_test.py`.


## M3 — качество ответов и оценка

| Задача | Статус | Что сделано / чем проверено |
|---|---|---|
| M3-T1 | **выполнена** | `eval/gold_questions.jsonl`: 46 вопросов, распределение 10/8/4/6/5/4/3/6; расширение формата `must_contain_any`; проверки уточнены по итогам baseline (ключи свойств, корни, idtf принципов, варианты отказа) |
| M3-T2 | **выполнена** | `tools/run_eval.py`: метрики accuracy / hallucinated / refusal, p50/p95/max, prompt/output tokens, VRAM, отчёт `.md` + сырой `.jsonl`; цель `make eval ARGS="..."` |
| M3-T3 | **выполнена** | три версии промпта (v1 → v2 → v3); `prompt_v3.md` закреплён в `Settings` и `.env.example`; рендер получил счётчики `типов: 16`, `свойств: 27`, `принципов: 5`; бюджет 3497/3500 токенов, тест зелёный |
| M3-T4 | **выполнена** | профиль A `qwen3.5:4b` — 100% / 0% / 100%; профиль B `qwen3.5:9b` — 100% / 0% / 100%, `100% GPU`, 6498 MiB; профиль C `gemma4:e4b` — 89.1% / 0% / 83.3%, не принят из-за отказов |
| M3-T5 | **выполнена** | `docs/03_EVAL.md`: методика, итерации, сравнение профилей, ограничения; отчёты в `eval/reports/` |

### Фактические результаты (финальная редакция gold)

| Профиль | accuracy | hall. | refusal | p50 / p95 | VRAM peak |
|---|---|---|---|---|---|
| A `qwen3.5:4b` | **100%** (46/46) | **0%** | **100%** (6/6) | 984 / 1443 мс | 4000 MiB |
| B `qwen3.5:9b` | **100%** (46/46) | **0%** | **100%** (6/6) | 1465 / 2224 мс | 6498 MiB |
| C `gemma4:e4b` | 89.1% (41/46) | 0% | 83.3% (5/6) | 486 / 733 мс | 4850 MiB |

Профиль A повторялся: 100% / 100% / 97.8% при нулевых галлюцинациях и 100% отказах.
После правки q021 (принимает idtf принципов) — снова 100%. Пороги 2.4 закрыты
всеми прогонами профилей A и B.

### Что изменилось в сервисе

- Вопрос с идентификатором вне контракта 3.6 не отправляется в LLM: детерминированный
  отказ `guard=unknown_identifier` (FR-13, NFR-11). Покрыто `test_service_guard.py`.
- `sanitize_question()` заменяет такие идентификаторы в копии вопроса для промпта;
  оригинал сохраняется в БЗ и журнале.
- few-shot дополнен примерами «перечисли все свойства» и отказа на просьбу придумать
  компонент; добавлено правило полноты этапов методики.
- sc-агент перезапущен после смены промпта/pack: лог подтверждает загрузку
  `prompt ~3497 токенов`, pack `2026-11-18T06:31:11Z`, регистрацию действия.
- `make test`: 51 unit-тест + контракт идентификаторов + typecheck панели — зелёные.

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

- **2026-11-18. M2: домен-тексты живут в `.scs`.** Принципы, методика и среда
  написаны в `kb/ui_assistant/*.scs`; `build_knowledge_pack.py` парсит их в
  `pack.json`. Иначе режимы `kb` и `fallback` давали бы разные ответы, а
  расхождение промпта было бы незаметно до M3.
- **2026-11-18. M2: единая строка рендера.** Generated `.scs` навешивает на
  классы ровно тот текст, который рендерится в промпт; `kb_reader` кладёт его
  в `item["kb_text"]`, `render` предпочитает его. Тест
  `test_generated_texts_match_pack_fallback` ловит расхождение.
- **2026-11-18. M2: per-item fallback.** Если в БЗ нет текста у отдельного
  класса, сервис берёт запись из pack и выставляет `kb.partial`/`kb.missing`,
  а не переключает весь источник в `fallback`. Полный `fallback` — только при
  недоступной sc-памяти.
- **2026-11-18. M2: методика — 1 процесс + 10 этапов.** Процесс хранится как
  экземпляр `concept_ui_knowledge`, этапы — как `concept_ui_development_stage`;
  `kb_reader` объединяет их в `methodology_stages`, сохраняя порядок.
- **2026-11-18. M2: роль — perm-pos дуга.** `py-sc-kpm` ищет `rrel_*` через
  `VAR_PERM_POS_ARC`, а `nrel_*` — через `VAR_COMMON_ARC`. Панель сначала
  создавала роли common arc; агент не видел аргументы. Исправлено и
  задокументировано в `docs/01_CONTRACTS.md`.
- **2026-11-18. M2: мягкая отмена в sc-memory.** Жёсткая отмена потребовала бы
  маркера в БЗ и слежения агентом; для этапа 1 панель просто перестаёт ждать,
  а агент дописывает ответ (AGENTS.md 3.11).

- **2026-11-18. M3: baseline обманул две проверки.** Часть gold всё ещё требовала
  дословные `concept_ui_*` там, где модель давала ключ свойства или корень слова.
  Проверки уточнены до семантических эквивалентов; реальные дефекты промпта
  (пропуск типа, отрицание общего свойства, эхо выдуманного id) исправлены отдельно.
- **2026-11-18. M3: счётчики вместо уговоров.** Просьбы «перечисли все» стабильно
  теряли последний элемент, пока в рендер не добавлены `типов: 16`,
  `свойств: 27`, `принципов: 5`. Модель стала сверяться с числом.
- **2026-11-18. M3: guard вместо лотереи.** Даже после санитизации вопроса модель
  иногда сама достраивала `concept_ui_chart` по слову «график». Вопросы с id вне
  контракта теперь вообще не доходят до LLM — это устранило нестабильность метрики.
- **2026-11-18. M3: few-shot с выдуманным id — плохая идея.** Пример с
  `concept_ui_timeline` протёк в ответ на вопрос про диаграмму Ганта. Пример
  переписан без выдуманного идентификатора.
- **2026-11-18. M3: дефолт run_eval.** Скрипт подставлял `prompt_v1.md`, игнорируя
  конфигурацию сервиса; исправлено — дефолт берётся из `Settings`. Все финальные
  отчёты явно показывают `prompt_v3.md / v3`.
- **2026-11-18. M3: профиль C быстр, но не точен.** `gemma4:e4b` влезает в 8 ГБ
  и даёт p95 < 1 с, однако проваливает 4 вопроса методики и один отказ; рабочим остаётся A,
  профиль B пригоден как альтернатива по качеству.

## Совместимость платформы (подтверждена на M2)

`py-sc-client 0.4.0` + `py-sc-kpm 0.4.0` успешно работают с `sc-machine 0.10.5`:
подключение, `ScKeynodes.resolve`, `search_by_template`, чтение 12 компонентов.
Блокирующий риск M0 не подтвердился и на M2: агент, запись диалога и
транспорт панели работают на этой связке. Версию платформы всё равно нужно
согласовать с командой (раздел 7 AGENTS.md).

## Блокеры

- нет
