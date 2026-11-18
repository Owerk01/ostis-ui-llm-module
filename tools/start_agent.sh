#!/usr/bin/env bash
# Запускает sc-агента в фоне (боевой режим sc-memory).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/.runtime/agent.pid"
LOG="$ROOT/service/logs/agent.log"
PATTERN='[o]stis_ui_assistant\.main'

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "sc-агент уже запущен через make (pid $(cat "$PID_FILE"))"
  exit 0
fi
if pgrep -f "$PATTERN" >/dev/null 2>&1; then
  echo "sc-агент уже запущен вне make; pid-файл не создаём"
  exit 0
fi
if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "ОШИБКА: окружение не создано. Выполните: make venv" >&2
  exit 1
fi

mkdir -p "$ROOT/.runtime" "$ROOT/service/logs"
setsid env ASSISTANT_TRANSPORT=sc-memory "$ROOT/.venv/bin/python" -u \
  -m ostis_ui_assistant.main >> "$LOG" 2>&1 < /dev/null &
PID=$!
echo "$PID" > "$PID_FILE"

for _ in $(seq 1 40); do
  if pgrep -f "$PATTERN" >/dev/null 2>&1; then
    echo "sc-агент запущен (pid $PID), лог: $LOG"
    exit 0
  fi
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "ОШИБКА: sc-агент завершился при старте. См. $LOG" >&2
    tail -30 "$LOG" >&2 || true
    exit 1
  fi
  sleep 0.25
done

echo "ОШИБКА: sc-агент не зарегистрировался за 10 с. См. $LOG" >&2
exit 1
