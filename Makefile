SHELL := /bin/bash
ROOT  := $(CURDIR)
VENV  := $(ROOT)/.venv
# pyenv-шим python3.12 может падать, если версия не активирована, поэтому берём явный путь.
PYTHON ?= $(shell test -x "$$HOME/.pyenv/versions/3.12.14/bin/python" && echo "$$HOME/.pyenv/versions/3.12.14/bin/python" || echo python3)
PY    := $(VENV)/bin/python

.DEFAULT_GOAL := help

.PHONY: help setup kb machine machine-stop ollama ollama-stop pull venv smoke \
        up down service panel pack kb-load test eval agent smoke-action

help:
	@echo "M0 (реализовано):"
	@echo "  make setup        — скачать официальные бинарники sc-machine 0.10.5 в .runtime/"
	@echo "  make kb           — собрать БЗ из external/ и kb/ в .runtime/kb.bin"
	@echo "  make machine      — запустить sc-machine нативно (порт 8090)"
	@echo "  make machine-stop — остановить sc-machine"
	@echo "  make ollama       — запустить Ollama с настройками из AGENTS.md 2.3"
	@echo "  make ollama-stop  — остановить Ollama, запущенный через make"
	@echo "  make pull         — скачать модель qwen3.5:4b"
	@echo "  make smoke        — смоук-тест чтения БЗ (M0-T6)"
	@echo "  make venv         — создать .venv и поставить зависимости сервиса"
	@echo "  make up / down    — поднять/остановить платформу M0"
	@echo "M1 (реализовано):"
	@echo "  make pack         — собрать knowledge/pack.json из каталога редактора"
	@echo "  make service      — запустить FastAPI direct-http на 127.0.0.1:8770"
	@echo "  make panel        — запустить dev-стенд панели на 127.0.0.1:5173"
	@echo "  make test         — pytest сервиса + typecheck панели"
	@echo "M2 (реализовано):"
	@echo "  make agent        — запустить sc-агент (ASSISTANT_TRANSPORT=sc-memory)"
	@echo "  make smoke-action — действие из скрипта: вопрос → ответ в БЗ"
	@echo "  make kb-load      — пересобрать БЗ с kb/ui_assistant и поднять sc-machine"
	@echo "M3: make eval"

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
	@$(VENV)/bin/pip install -q -r tools/requirements-m0.txt
	@$(VENV)/bin/pip install -q -e "./service[dev]"
	@echo "Окружение готово: $(VENV)"

smoke: venv
	@$(PY) tools/kb_smoke_test.py

# Повторный up не пересобирает БЗ (это ~3 мин); для пересборки есть make kb.
up: setup ollama pull
	@if [ ! -d .runtime/kb.bin ]; then \
		$(MAKE) machine-stop kb; \
	fi
	@$(MAKE) machine
	@echo "Платформа M0 готова: sc-machine 8090, Ollama 11434, модель qwen3.5:4b"

down: machine-stop
	@echo "sc-machine остановлена. Ollama оставлена запущенной; для остановки: make ollama-stop"

pack: venv
	@$(PY) tools/build_knowledge_pack.py
	@$(PY) tools/generate_kb_scs.py
	@$(PY) tools/check_id_collisions.py

service: venv
	@test -f .env || echo "WARN: .env не найден, используются значения по умолчанию из .env.example" >&2
	@$(PY) -m ostis_ui_assistant.main

agent: venv
	@test -f .env || echo "WARN: .env не найден, используются значения по умолчанию из .env.example" >&2
	@echo "sc-агент: action_answer_ui_development_question (Ctrl+C — остановить)"
	@ASSISTANT_TRANSPORT=sc-memory $(PY) -m ostis_ui_assistant.main

smoke-action: venv
	@$(PY) tools/action_smoke_test.py "$(or $(Q),Что такое concept_ui_button?)"

panel:
	@cd panel && if [ ! -d node_modules ]; then npm install --no-audit --no-fund; fi
	@cd panel && npm run dev

kb-load: machine-stop
	@bash tools/build_kb.sh
	@$(MAKE) machine
	@$(MAKE) smoke

test: venv
	@$(PY) tools/check_id_collisions.py
	@$(VENV)/bin/pytest -q service/tests
	@if [ -d panel/node_modules ]; then \
		cd panel && npm run typecheck; \
	else \
		echo "WARN: panel/node_modules отсутствует, typecheck панели пропущен (make panel)" >&2; \
	fi

eval:
	@echo "Будет реализовано в M3 (gold-набор)." >&2; exit 1
