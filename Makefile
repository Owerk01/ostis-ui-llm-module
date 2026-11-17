SHELL := /bin/bash
ROOT  := $(CURDIR)
VENV  := $(ROOT)/.venv
# pyenv-шим python3.12 может падать, если версия не активирована, поэтому берём явный путь.
PYTHON ?= $(shell test -x "$$HOME/.pyenv/versions/3.12.14/bin/python" && echo "$$HOME/.pyenv/versions/3.12.14/bin/python" || echo python3)
PY    := $(VENV)/bin/python

.DEFAULT_GOAL := help

.PHONY: help setup kb machine machine-stop ollama ollama-stop pull venv smoke \
        up down service panel pack kb-load test eval

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
	@echo "  make venv         — создать .venv и поставить зависимости смоука"
	@echo "  make up / down    — поднять/остановить платформу M0"
	@echo "M1/M2 (пока заглушки): make service / panel / pack / kb-load / test / eval"

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

service:
	@echo "Будет реализовано в M1 (FastAPI-сервис)." >&2; exit 1

panel:
	@echo "Будет реализовано в M1 (панель чата)." >&2; exit 1

pack:
	@echo "Будет реализовано в M1-T2 (knowledge pack)." >&2; exit 1

kb-load:
	@echo "Полная загрузка нашего фрагмента в БЗ — M2-T5; сейчас используется make kb." >&2; exit 1

test:
	@echo "Будет реализовано в M1/M2 (pytest + проверка коллизий)." >&2; exit 1

eval:
	@echo "Будет реализовано в M3 (gold-набор)." >&2; exit 1
