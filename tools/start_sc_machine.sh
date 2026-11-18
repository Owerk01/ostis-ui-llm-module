#!/usr/bin/env bash
# Запускает sc-machine в фоне (нативно, без Docker).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PID_FILE="${SC_PID_FILE:-$ROOT/.runtime/sc-machine.pid}"
BIN="$ROOT/.runtime/sc-machine/bin/sc-machine"
STORAGE="${SC_STORAGE:-$ROOT/.runtime/kb.bin}"
CONFIG="$ROOT/platform/sc-machine.ini"
LOG="$ROOT/service/logs/sc-machine.stdout.log"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "sc-machine уже запущена (pid $(cat "$PID_FILE"))"
  exit 0
fi

if [ ! -x "$BIN" ]; then
  echo "ОШИБКА: sc-machine не найдена. Выполните: make setup" >&2
  exit 1
fi
if [ ! -d "$STORAGE" ]; then
  echo "ОШИБКА: БЗ не собрана. Выполните: make kb" >&2
  exit 1
fi

mkdir -p "$ROOT/service/logs"
nohup "$BIN" -s "$STORAGE" -e "$ROOT/.runtime/sc-machine/lib/extensions" -c "$CONFIG" >> "$LOG" 2>&1 &
echo $! > "$PID_FILE"

for _ in $(seq 1 60); do
  if (exec 3<>/dev/tcp/127.0.0.1/8090) 2>/dev/null; then
    exec 3>&- 3<&-
    echo "sc-machine слушает 127.0.0.1:8090 (pid $(cat "$PID_FILE"))"
    exit 0
  fi
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "ОШИБКА: sc-machine завершилась при старте. См. $LOG" >&2
    tail -30 "$LOG" >&2 || true
    exit 1
  fi
  sleep 0.5
done

echo "ОШИБКА: sc-machine не открыла порт 8090 за 30 с. См. $LOG" >&2
exit 1
