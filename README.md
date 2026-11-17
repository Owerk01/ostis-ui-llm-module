# ostis-ui-assistant

Ассистент разработчика пользовательских интерфейсов (ПИ) для инструментальной
среды OSTIS. Этап 1: локальная LLM + связь с базой знаний через sc-память.

Контракт этапа — [`AGENTS.md`](AGENTS.md). Ход работ — [`PROGRESS.md`](PROGRESS.md).

> Сейчас реализована веха **M0** (подготовка и смоук платформы).
> Сервис, панель и knowledge pack появятся в M1–M2.

## Что уже работает в M0

- каркас репозитория;
- read-only клоны `external/` с зафиксированными коммитами;
- нативный `sc-machine 0.10.5` без Docker и sudo (`.runtime/`);
- сборка БЗ из `external/ostis-example-app` + схемы UI редактора и примеров;
- смоук-тест `tools/kb_smoke_test.py`: читает `ex_login` и типы компонентов;
- локальная LLM: `qwen3.5:4b` через Ollama (настройки из AGENTS.md, раздел 2.3).

## Быстрый старт (Linux, M0)

Требования: Python 3.12, `git`, `curl`, `zstd`, Ollama (или установите его
пользовательски, см. ниже).

```bash
cp .env.example .env

make setup        # скачать sc-machine 0.10.5 в .runtime/
make kb           # собрать БЗ
make machine      # запустить sc-machine на 127.0.0.1:8090
make ollama       # запустить Ollama с нужными переменными
make pull         # скачать qwen3.5:4b
make smoke        # проверить чтение БЗ
```

Остановка:

```bash
make down         # остановить sc-machine
make ollama-stop  # остановить Ollama, если он запущен через make
```

### Установка Ollama без sudo

Если системного Ollama нет и нет прав root:

```bash
curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst \
  | tar --zstd -xf - -C "$HOME/.local"
~/.local/bin/ollama --version
```

`make ollama` найдёт `~/.local/bin/ollama` автоматически.

## Структура

```
external/            read-only клоны репозиториев команды (gitignore)
platform/            repo.path и конфигурация sc-machine
knowledge/           provenance; pack.json появится в M1
kb/ui_assistant/     наши конструкции диалога и знаний (M2)
tools/               setup, сборка БЗ, смоук, будущие pack/eval
service/             Python-сервис (M1–M2)
panel/               панель чата React (M1)
docs/                контракты, знания, методика оценки
```

## Важно

- `external/` не редактируется; схема UI не копируется и не переопределяется.
- На этапе 1 ассистент **не изменяет** модель интерфейса.
- Для запуска не требуется Docker.
