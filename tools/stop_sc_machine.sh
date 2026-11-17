#!/usr/bin/env bash
# Останавливает sc-machine, запущенную через tools/start_sc_machine.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/.runtime/sc-machine.pid"

if [ ! -f "$PID_FILE" ]; then
  echo "sc-machine не запущена (pid-файла нет)"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  for _ in $(seq 1 40); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.25
  done
  kill -0 "$PID" 2>/dev/null && kill -9 "$PID" || true
  echo "sc-machine остановлена (pid $PID)"
else
  echo "Процесс $PID уже завершён"
fi
rm -f "$PID_FILE"
