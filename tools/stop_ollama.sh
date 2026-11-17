#!/usr/bin/env bash
# Останавливает только тот Ollama, который запущен через tools/start_ollama.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/.runtime/ollama.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "Ollama не запускалась через make ollama (pid-файла нет)"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "Ollama остановлена (pid $PID)"
else
  echo "Процесс $PID уже завершён"
fi
rm -f "$PID_FILE"
