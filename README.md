# ostis-ui-assistant

Ассистент разработчика пользовательских интерфейсов (ПИ) для инструментальной
среды OSTIS. Этап 1: локальная LLM + связь с базой знаний через sc-память.

Контракт этапа — [`AGENTS.md`](AGENTS.md). Ход работ — [`PROGRESS.md`](PROGRESS.md).

> Реализованы вехи **M0** (платформа), **M1** (локальная модель, knowledge
> pack, FastAPI-сервис, панель) и **M2** (знания в БЗ, sc-агент, транспорт
> `sc-memory`). Работают:
> - боевой режим `sc-memory`: панель → действие в БЗ → sc-агент → LLM →
>   ответ и журнал в БЗ → панель;
> - отладочный режим `direct-http` с потоковым SSE;
> - ответы по каталогу (16 типов, 27 свойств, 4 отношения), 5 принципов,
>   методика и устройство среды;
> - пост-валидация идентификаторов и чипы оснований;
> - отмена, таймауты, ошибки LLM, повтор запроса.
>
> В M3 — gold-набор и метрики качества, в M4 — встраивание и финальная
> документация.

## Быстрый старт (Linux)

Требования: Python 3.12, Node 20+, `git`, `curl`, `zstd`, Ollama (можно
пользовательски, см. ниже).

```bash
cp .env.example .env

make setup        # скачать sc-machine 0.10.5 в .runtime/
make kb           # собрать БЗ (первый раз ~3 мин)
make machine      # sc-machine на 127.0.0.1:8090
make ollama       # Ollama с настройками из AGENTS.md 2.3
make pull         # qwen3.5:4b (если ещё нет)

make pack         # knowledge/pack.json + generated .scs из каталога редактора
make kb-load      # пересобрать БЗ с kb/ui_assistant и поднять sc-machine
make agent        # sc-агент (боевой режим sc-memory, отдельный терминал)
make panel        # панель на http://localhost:5173/ (отдельный терминал)
```

Открыть `http://localhost:5173/`, выбрать транспорт `sc-memory` (он выбран по
умолчанию), задать вопрос, например «Чем `concept_ui_button` отличается от
`concept_ui_menu_item`?». Запрос и ответ сохраняются в БЗ.

Отладочный режим вместо агента:

```bash
make service      # FastAPI на 127.0.0.1:8770
```

и переключить транспорт в dev-стенде на `direct-http`.

Проверка:

```bash
make test         # pytest сервиса + коллизии идентификаторов + typecheck панели
make smoke        # чтение БЗ (нужна sc-machine)
make smoke-action # действие из скрипта → ответ в БЗ (нужен make agent)
E2E_MODE=sc-memory .venv/bin/python tools/e2e_panel.py   # headless Chrome
```

Повторный `make up` не пересобирает БЗ и не скачивает модель заново;
для пересборки БЗ — `make kb` (sc-machine должна быть остановлена).

Остановка:

```bash
make down         # остановить sc-machine
make ollama-stop  # остановить Ollama, если запущен через make
```

### Установка Ollama без sudo

```bash
curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst \
  | tar --zstd -xf - -C "$HOME/.local"
~/.local/bin/ollama --version
```

`make ollama` найдёт `~/.local/bin/ollama` автоматически.

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
