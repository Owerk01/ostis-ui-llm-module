#!/usr/bin/env bash
# Запускает локальный Ollama с настройками из раздела 2.3 AGENTS.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/.runtime/ollama.pid"

resolve_ollama() {
  if command -v ollama >/dev/null 2>&1; then
    command -v ollama
  elif [ -x "$HOME/.local/bin/ollama" ]; then
    echo "$HOME/.local/bin/ollama"
  else
    echo ""
  fi
}

OLLAMA_BIN="$(resolve_ollama)"
if [ -z "$OLLAMA_BIN" ]; then
  echo "ОШИБКА: ollama не найдена. Установите Ollama (см. README)." >&2
  exit 1
fi

if curl -fsS --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama уже отвечает на 127.0.0.1:11434"
  exit 0
fi

mkdir -p "$ROOT/.runtime" "$ROOT/service/logs"
nohup env \
  OLLAMA_CONTEXT_LENGTH=8192 \
  OLLAMA_KV_CACHE_TYPE=q8_0 \
  OLLAMA_FLASH_ATTENTION=1 \
  OLLAMA_MAX_LOADED_MODELS=1 \
  OLLAMA_NUM_PARALLEL=1 \
  OLLAMA_KEEP_ALIVE=30m \
  "$OLLAMA_BIN" serve >> "$ROOT/service/logs/ollama.log" 2>&1 &
echo $! > "$PID_FILE"

for _ in $(seq 1 60); do
  if curl -fsS --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "Ollama запущена (pid $(cat "$PID_FILE"))"
    exit 0
  fi
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "ОШИБКА: Ollama завершилась при старте. См. service/logs/ollama.log" >&2
    tail -30 "$ROOT/service/logs/ollama.log" >&2 || true
    exit 1
  fi
  sleep 0.5
done

echo "ОШИБКА: Ollama не открыла порт 11434 за 30 с" >&2
exit 1
