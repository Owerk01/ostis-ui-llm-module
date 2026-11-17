#!/usr/bin/env bash
# Скачивает модель, только если её ещё нет локально (не тормозит повторный make up).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL="${LLM_MODEL:-qwen3.5:4b}"

if command -v ollama >/dev/null 2>&1; then
  OLLAMA_BIN="$(command -v ollama)"
elif [ -x "$HOME/.local/bin/ollama" ]; then
  OLLAMA_BIN="$HOME/.local/bin/ollama"
else
  echo "ОШИБКА: ollama не найдена. Установите Ollama (см. README)." >&2
  exit 1
fi

if "$OLLAMA_BIN" list 2>/dev/null | awk 'NR > 1 {print $1}' | grep -Fxq "$MODEL"; then
  echo "Модель $MODEL уже загружена"
  exit 0
fi

echo "Загрузка модели $MODEL ..."
"$OLLAMA_BIN" pull "$MODEL"
