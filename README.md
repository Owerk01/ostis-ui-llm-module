# ostis-ui-assistant

Ассистент разработчика пользовательских интерфейсов (ПИ) для инструментальной
среды OSTIS. Этап 1: локальная LLM + связь с базой знаний через sc-память.

Контракт этапа — [`AGENTS.md`](AGENTS.md). Ход работ — [`PROGRESS.md`](PROGRESS.md).

> Реализованы **все вехи этапа 1 (M0–M4)**. Работают:
> - боевой режим `sc-memory`: панель → действие в БЗ → sc-агент → LLM →
>   ответ и журнал в БЗ → панель;
> - отладочный режим `direct-http` с потоковым SSE;
> - ответы по каталогу (16 типов, 27 свойств, 4 отношения), 5 принципов,
>   методика и устройство среды;
> - пост-валидация идентификаторов, guard неизвестных id и чипы оснований;
> - отмена, таймауты, ошибки LLM, повтор запроса;
> - gold-набор 46 вопросов: Accuracy 100%, галлюцинаций 0, отказы 100%
>   (профиль A `qwen3.5:4b`, подробности — `docs/03_EVAL.md`);
> - панель как изолированная библиотека (`npm run build:lib`) для встраивания в редактор.

## Быстрый старт (Linux / WSL2)

Требования: **Linux x86_64**, Python 3.12, Node 20+, `git`, `curl`, `zstd`,
Ollama. Docker не нужен.

### 1. Источники истины (только для чтения)

```bash
mkdir -p external && cd external
git clone https://github.com/vodo4kin/ostis-ui-editor
git -C ostis-ui-editor checkout f6eb4fa
git clone -b feature/SCS_to_HTML https://github.com/Glentas/ostis-ui
git -C ostis-ui checkout a673766
git clone https://github.com/Oddchew/UI-adaptation
git -C UI-adaptation checkout 5c3d627
git clone -b 0.10.0 https://github.com/ostis-apps/ostis-example-app
cd ..
```

Коммиты зафиксированы в `knowledge/provenance.json`. `external/` в `.gitignore`.

### 2. Один командой

```bash
cp .env.example .env
make up
```

`make up` ставит зависимости, скачивает sc-machine 0.10.5 и модель
`qwen3.5:4b` (если их нет), собирает pack и БЗ, поднимает sc-machine,
sc-агента и панель. Повторный запуск ничего не пересобирает.

Открыть **http://127.0.0.1:5173/**, транспорт `sc-memory` выбран по умолчанию.
Вопрос для проверки: «Чем `concept_ui_button` отличается от `concept_ui_menu_item`?».

### 3. Пошагово (для отладки)

```bash
make venv          # .venv и зависимости
make setup         # sc-machine 0.10.5 в .runtime/
make ollama        # Ollama с настройками из AGENTS.md 2.3
make pull          # qwen3.5:4b, если ещё нет
make pack          # pack.json + generated .scs + проверка коллизий
make kb-load       # собрать БЗ с kb/ui_assistant и поднять sc-machine
make agent         # sc-агент в текущем терминале
make panel         # Vite в текущем терминале
```

Отладочный режим вместо агента — `make service` (FastAPI на 127.0.0.1:8770)
и переключатель `direct-http` в dev-стенде.

### 4. Проверки и остановка

```bash
make test         # pytest + проверка коллизий идентификаторов + typecheck панели
make smoke        # чтение БЗ (нужна sc-machine)
make smoke-action # действие → ответ в БЗ (нужен агент)
make eval ARGS="--label final"   # gold-набор и метрики
make build-lib    # библиотека панели в panel/dist-lib
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

## Сервис direct-http (M1)

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
так гарантируется отсутствие выдуманных идентификаторов (FR-13).

## Панель

Панель — изолированный React-компонент `<AssistantPanel transport={...} />`.
Инструкция встраивания, props и правила изоляции стилей — [`panel/README.md`](panel/README.md).
Dev-стенд позволяет сменить адрес сервиса и проверить `onSourceClick`.

## Структура

```
external/            read-only клоны репозиториев команды (gitignore)
platform/            repo.path и конфигурация sc-machine
knowledge/           pack.json, provenance.json, prompt_v*.md (текущий v3), purpose_overrides.json
kb/ui_assistant/     наши конструкции диалога и знаний + generated тексты каталога
tools/               setup, сборка БЗ, pack, смоук
service/             Python-сервис: LLM, знания, валидация, FastAPI
panel/               панель чата React + dev-стенд
docs/                контракты, знания, методика оценки, скриншоты
eval/                gold-набор и отчёты (M3)
```

## Важно

- `external/` не редактируется; схема UI не копируется и не переопределяется.
- На этапе 1 ассистент **не изменяет** модель интерфейса и не вызывает
  `action_translate_sc_to_html`.
- В режиме `sc-memory` знания читаются из БЗ (`kb`) и только при её
  недоступности берутся из `knowledge/pack.json` (`fallback`, с явной пометкой
  в панели и `/health`).
- Для запуска не требуется Docker.
