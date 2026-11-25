SHELL := /bin/bash
ROOT  := $(CURDIR)
VENV  := $(ROOT)/.venv
# pyenv-шим python3.12 может падать, если версия не активирована, поэтому берём явный путь.
PYTHON ?= $(shell test -x "$$HOME/.pyenv/versions/3.12.14/bin/python" && echo "$$HOME/.pyenv/versions/3.12.14/bin/python" || echo python3)
PY    := $(VENV)/bin/python

.DEFAULT_GOAL := help

.PHONY: help setup kb machine machine-stop ollama ollama-stop pull venv smoke \
        up down service panel pack kb-load kb-load-noschema test eval agent agent-start agent-stop \
        panel-start panel-stop smoke-action drift build-transport integration-check

help:
	@echo "Платформа:"
	@echo "  make setup        — скачать официальные бинарники sc-machine 0.10.5 в .runtime/"
	@echo "  make kb           — собрать БЗ из external/ и kb/ в .runtime/kb.bin"
	@echo "  make machine      — запустить sc-machine нативно (порт 8090)"
	@echo "  make machine-stop — остановить sc-machine"
	@echo "  make ollama       — запустить Ollama с рекомендованными настройками"
	@echo "  make ollama-stop  — остановить Ollama, запущенный через make"
	@echo "  make pull         — скачать модель qwen3.5:4b"
	@echo "  make smoke        — смоук-тест чтения БЗ"
	@echo "  make venv         — создать .venv и поставить зависимости сервиса"
	@echo "  make up / down    — поднять/остановить весь стек (sc-machine, Ollama, агент, панель)"
	@echo "Сервис и знания:"
	@echo "  make pack         — собрать knowledge/pack.json из каталога редактора"
	@echo "  make service      — запустить FastAPI direct-http на 127.0.0.1:8770"
	@echo "  make panel        — запустить dev-стенд панели на 127.0.0.1:5173"
	@echo "  make agent        — запустить sc-агент (ASSISTANT_TRANSPORT=sc-memory)"
	@echo "  make smoke-action — действие из скрипта: вопрос → ответ в БЗ"
	@echo "  make kb-load      — пересобрать БЗ с kb/ui_assistant и поднять sc-machine"
	@echo "  make kb-load-noschema — БЗ без схемы UI для теста read-пути"
	@echo "Проверки и сборка:"
	@echo "  make test         — pytest сервиса + typecheck панели"
	@echo "  make eval         — прогон gold-набора и отчёт (ARGS=\"--label ...\")"
	@echo "  make build-lib    — собрать панель как библиотеку (dist-lib)"
	@echo "  make build-transport — собрать транспорт без React (dist-transport)"
	@echo "  make integration-check — внешний TS-клиент: health → ask → ответ из БЗ"
	@echo "  make agent-start / panel-start / agent-stop / panel-stop — фоновый запуск"

setup:
	@bash tools/setup_platform.sh

kb:
	@bash tools/build_kb.sh

machine:
	@bash tools/start_sc_machine.sh

machine-stop:
	@bash tools/stop_sc_machine.sh

ollama:
	@bash tools/start_ollama.sh

ollama-stop:
	@bash tools/stop_ollama.sh

pull: ollama
	@bash tools/pull_model.sh

venv:
	@test -d "$(VENV)" || $(PYTHON) -m venv "$(VENV)"
	@$(VENV)/bin/pip install -q -U pip
	@$(VENV)/bin/pip install -q -r tools/requirements.txt
	@$(VENV)/bin/pip install -q -e "./service[dev]"
	@echo "Окружение готово: $(VENV)"

smoke: venv
	@$(PY) tools/kb_smoke_test.py

# Повторный up не пересобирает БЗ (это ~3 мин); для пересборки есть make kb-load.
up: setup ollama pull pack
	@if [ ! -d .runtime/kb.bin ]; then \
		$(MAKE) machine-stop kb; \
	fi
	@$(MAKE) machine
	@$(MAKE) agent-start
	@$(MAKE) panel-start
	@echo "Стек готов: sc-machine 8090, Ollama 11434, агент, панель 127.0.0.1:5173"

down: panel-stop agent-stop machine-stop
	@echo "Стек остановлен. Ollama оставлена запущенной; для остановки: make ollama-stop"

pack: venv
	@$(PY) tools/build_knowledge_pack.py
	@$(PY) tools/generate_kb_scs.py
	@$(PY) tools/check_id_collisions.py

drift: venv
	@$(PY) tools/check_upstream_drift.py

service: venv
	@test -f .env || echo "WARN: .env не найден, используются значения по умолчанию из .env.example" >&2
	@$(PY) -m ostis_ui_assistant.main

agent: venv
	@test -f .env || echo "WARN: .env не найден, используются значения по умолчанию из .env.example" >&2
	@echo "sc-агент: action_answer_ui_development_question (Ctrl+C — остановить)"
	@ASSISTANT_TRANSPORT=sc-memory $(PY) -m ostis_ui_assistant.main

smoke-action: venv
	@$(PY) tools/action_smoke_test.py "$(or $(Q),Что такое concept_ui_button?)"

agent-start: venv
	@bash tools/start_agent.sh

agent-stop:
	@bash tools/stop_agent.sh

panel-start:
	@bash tools/start_panel.sh

panel-stop:
	@bash tools/stop_panel.sh

build-lib:
	@cd panel && npm run build:lib

build-transport:
	@cd panel && if [ ! -d node_modules ]; then npm ci --no-audit --no-fund; fi
	@cd panel && npm run build:transport

integration-check: build-transport
	@node --experimental-strip-types tools/integration-check.ts

panel:
	@cd panel && if [ ! -d node_modules ]; then npm install --no-audit --no-fund; fi
	@cd panel && npm run dev

kb-load: machine-stop
	@bash tools/build_kb.sh
	@$(MAKE) machine
	@$(MAKE) smoke

# БЗ без схемы UI — для интеграционного теста read-пути (FIX-P0-1).
kb-load-noschema: machine-stop
	@KB_OUTPUT=$(ROOT)/.runtime/kb-noschema.bin KB_REPO_PATH=platform/repo.path.assistant-only \
		bash tools/build_kb.sh
	@SC_STORAGE=$(ROOT)/.runtime/kb-noschema.bin SC_PID_FILE=$(ROOT)/.runtime/sc-machine-noschema.pid \
		bash tools/start_sc_machine.sh
	@echo "БЗ без схемы UI готова: .runtime/kb-noschema.bin (порт 8090)"

test: venv
	@$(PY) tools/check_id_collisions.py
	@$(PY) tools/check_upstream_drift.py
	@$(VENV)/bin/pytest -q service/tests
	@if [ -d panel/node_modules ]; then \
		cd panel && npm run typecheck && npm test; \
	else \
		echo "WARN: panel/node_modules отсутствует, проверки панели пропущены (make panel)" >&2; \
	fi

eval: venv
	@$(PY) tools/run_eval.py $(ARGS)
