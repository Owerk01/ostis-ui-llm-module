# ostis-ui-assistant

Ассистент разработчика пользовательских интерфейсов (ПИ) для инструментальной
среды OSTIS. Локальная LLM + связь с базой знаний через sc-память.

Документация: [контракты](docs/01_CONTRACTS.md),
[знания](docs/02_KNOWLEDGE.md), [оценка качества](docs/03_EVAL.md),
[интеграция](docs/04_INTEGRATION.md).

> Реализовано:
> - боевой режим `sc-memory`: панель → действие в БЗ → sc-агент → LLM →
>   ответ и журнал в БЗ → панель;
> - отладочный режим `direct-http` с потоковым SSE;
> - ответы по каталогу (16 типов, 27 свойств, 6 отношений), 5 принципов,
>   методика и устройство среды;
> - пост-валидация идентификаторов, guard неизвестных id и чипы оснований;
> - ответ на языке вопроса и защита от раскрытия внутренних правил промпта;
> - отмена, таймауты, ошибки LLM, повтор запроса;
> - обработка вопроса вне потока событий: ограниченная очередь, pending-сообщение,
>   watchdog висячих действий;
> - один экземпляр агента на БЗ (advisory-аренда с heartbeat), порядок сообщений
>   из БЗ;
> - контекст последних 6 сообщений диалога (`DIALOG_HISTORY_TURNS`) для анафоры,
>   не долговременная память;
> - оценка на HEAD по dev/holdout: автопроверки 92.3% / 88.2%, фактическая
>   точность 96.5%, невыполненные пороги перечислены в `docs/03_EVAL.md`;
> - транспорт как отдельный пакет без React (`npm run build:transport`),
>   внешний TS-клиент получает ответ из БЗ (`make integration-check`);

> **AssistantPanel — эталонный dev-стенд, не продуктовый UI.** Продуктовый чат
> делает редактор, подключая standalone-транспорт
> `ostis-ui-assistant-dialog-transport` (peerDependency только `ts-sc-client`).

**Статус: готов к интеграции по [`docs/04_INTEGRATION.md`](docs/04_INTEGRATION.md).**
Известные расхождения и невыполненные пороги оценки — [`docs/03_EVAL.md`](docs/03_EVAL.md).

## Быстрый старт (Linux / WSL2)

Требования: **Linux x86_64**, Python 3.12, Node 20+, `git`, `curl`, `zstd`,
Ollama. Docker не нужен.

### 1. Один командой

```bash
cp .env.example .env
make up
```

`make up` ставит зависимости, скачивает sc-machine 0.10.5 и модель
`qwen3.5:4b` (если их нет), собирает pack и БЗ, поднимает sc-machine,
sc-агента и панель. Повторный запуск ничего не пересобирает.

Открыть **http://127.0.0.1:5173/**, транспорт `sc-memory` выбран по умолчанию.
Вопрос для проверки: «Чем `concept_ui_button` отличается от `concept_ui_menu_item`?».

### 2. Пошагово (для отладки)

```bash
make venv          # .venv и зависимости
make setup         # sc-machine 0.10.5 в .runtime/
make ollama        # Ollama с рекомендованными настройками контекста и KV
make pull          # qwen3.5:4b, если ещё нет
make pack          # pack.json + generated .scs + проверка коллизий
make kb-load       # собрать БЗ с kb/ui_assistant и поднять sc-machine
make agent         # sc-агент в текущем терминале
make panel         # Vite в текущем терминале
```

Отладочный режим вместо агента — `make service` (FastAPI на 127.0.0.1:8770)
и переключатель `direct-http` в dev-стенде.

### 3. Проверки и остановка

```bash
make test         # pytest + проверка коллизий идентификаторов + typecheck панели
make smoke        # чтение БЗ (нужна sc-machine)
make smoke-action # действие → ответ в БЗ (нужен агент)
make eval ARGS="--label profile-a-final"   # gold-набор и метрики
make build-lib    # библиотека панели в panel/dist-lib (React, dev-стенд)
make build-transport  # транспорт без React в panel/dist-transport
make integration-check # внешний TS-скрипт: health → ask → ответ из БЗ
E2E_MODE=sc-memory .venv/bin/python tools/e2e_panel.py   # headless Chrome

make down         # панель, агент и sc-machine
make ollama-stop  # Ollama, если запущена через make
```

Пересборка БЗ после правок `.scs`: `make kb-load` (sc-machine будет остановлена).

### Установка Ollama без sudo

```bash
curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst \
  | tar --zstd -xf - -C "$HOME/.local"
~/.local/bin/ollama --version
```

`make ollama` найдёт `~/.local/bin/ollama` автоматически.

## Быстрый старт (Windows 10/11)

Скрипты платформы — bash, а sc-machine поставляется только для Linux x86_64,
поэтому используйте **WSL2**:

```powershell
wsl --install -d Ubuntu-24.04
# после перезагрузки откройте Ubuntu и выполните все шаги раздела Linux:
sudo apt update && sudo apt install -y python3.12 python3.12-venv git curl zstd
curl -fsSL https://ollama.com/install.sh | sh
```

Далее в терминале WSL — те же команды `git clone …`, `cp .env.example .env`,
`make up`. Порты WSL пробрасываются в Windows автоматически, поэтому панель
открывается и из Windows-браузера на `http://127.0.0.1:5173/`.

Если Ollama установлена на Windows-хосте, запустите её с `OLLAMA_HOST=0.0.0.0`
и в `.env` WSL укажите `LLM_BASE_URL=http://<IP-хоста>:11434`.

## Сервис direct-http

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/health` | модель, LLM, источник знаний, версия pack |
| `POST` | `/dialog` | создать диалог |
| `POST` | `/ask` | вопрос, ответ потоком SSE |
| `GET` | `/history/{dialog_id}` | история диалога в памяти сервиса |
| `POST` | `/cancel` | мягкая отмена |

Проверка без панели:

```bash
curl -s http://127.0.0.1:8770/health | python -m json.tool
curl -sN -X POST http://127.0.0.1:8770/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Что задаёт свойство action_id?"}'
```

События SSE: `meta`, `delta`, `done`, `cancelled`, `error`.
Ответ сначала генерируется и валидируется целиком, затем отдаётся кусками:
так гарантируется отсутствие выдуманных идентификаторов.

Для вопросов с анафорой (`«а какие у него свойства?»`) в промпт добавляются
последние `DIALOG_HISTORY_TURNS` завершённых сообщений (по умолчанию 6, бюджет
800 токенов, самые старые отбрасываются первыми). Текущий вопрос и pending
исключаются; это не долговременная память и не замена знаниям из БЗ.

## Контекст экземпляра интерфейса

Вопрос может относиться к конкретному интерфейсу или выделенному компоненту.
Редактор передаёт контекст через `ask(dialogId, question, { context })`, где
`context = { mode: 'none' | 'selection' | 'whole', interfaceId?, componentIds? }`.
Ассистент читает экземпляр из БЗ **только на чтение** (`nrel_ui_id`,
`nrel_ui_has_component`, `nrel_ui_input_target` / `nrel_ui_output_target`),
добавляет отдельный блок `ЭКЗЕМПЛЯР` в промпт и ссылается на реальные `ex_*` /
`*_cmp_*` в основаниях. Изменение экземпляров, вызов транслятора и предпросмотр
остаются за редактором. Идентификаторы экземпляра из вопроса не становятся
основаниями без чтения из БЗ: неизвестные `cmp_*` вырезаются валидатором.

Пример и полная последовательность вызовов — [`docs/04_INTEGRATION.md`](docs/04_INTEGRATION.md).

## Панель

Панель — изолированный React-компонент `<AssistantPanel transport={...} />`.
Инструкция встраивания, props и правила изоляции стилей — [`panel/README.md`](panel/README.md).
Dev-стенд позволяет сменить адрес сервиса и проверить `onSourceClick`.

## Структура

```
external/            read-only клоны репозиториев команды (gitignore)
platform/            repo.path и конфигурация sc-machine
knowledge/           pack.json, provenance.json, prompt_v*.md (текущий v5), purpose_overrides.json
kb/ui_assistant/     наши конструкции диалога и знаний + generated тексты каталога
tools/               setup, сборка БЗ, pack, смоук
service/             Python-сервис: LLM, знания, валидация, FastAPI
panel/               панель чата React + dev-стенд и standalone-транспорт
docs/                контракты, знания, методика оценки, скриншоты
eval/                gold-набор и отчёты прогонов
```
