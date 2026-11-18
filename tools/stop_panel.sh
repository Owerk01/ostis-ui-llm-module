#!/usr/bin/env bash
# Останавливает только панель, запущенную через tools/start_panel.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/.runtime/panel.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "Панель не запускалась через make (pid-файла нет)"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill -TERM -- "-$PID" 2>/dev/null || kill -TERM "$PID" || true
  for _ in $(seq 1 40); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$PID" 2>/dev/null; then
    kill -KILL -- "-$PID" 2>/dev/null || kill -KILL "$PID" || true
  fi
  echo "Панель остановлена (pid $PID)"
else
  echo "Процесс $PID уже завершён"
fi
rm -f "$PID_FILE"
