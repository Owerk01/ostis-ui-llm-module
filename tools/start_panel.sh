#!/usr/bin/env bash
# Запускает dev-сервер панели в фоне.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT/.runtime/panel.pid"
LOG="$ROOT/service/logs/panel.log"
URL="http://127.0.0.1:5173/"

if curl -fsS --max-time 2 "$URL" >/dev/null 2>&1; then
  echo "Панель уже отвечает на $URL"
  exit 0
fi
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Панель уже запущена через make (pid $(cat "$PID_FILE"))"
  exit 0
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "ОШИБКА: npm не найден. Установите Node 20+" >&2
  exit 1
fi

if [ ! -d "$ROOT/panel/node_modules" ]; then
  echo "Установка зависимостей панели ..."
  (cd "$ROOT/panel" && npm ci --no-audit --no-fund)
fi

mkdir -p "$ROOT/.runtime" "$ROOT/service/logs"
setsid env ROOT="$ROOT" bash -c 'cd "$ROOT/panel" && exec npm run dev' \
  >> "$LOG" 2>&1 < /dev/null &
PID=$!
echo "$PID" > "$PID_FILE"

for _ in $(seq 1 120); do
  if curl -fsS --max-time 2 "$URL" >/dev/null 2>&1; then
    echo "Панель готова: $URL (pid $PID), лог: $LOG"
    exit 0
  fi
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "ОШИБКА: Vite завершился при старте. См. $LOG" >&2
    tail -30 "$LOG" >&2 || true
    exit 1
  fi
  sleep 0.5
done

echo "ОШИБКА: панель не открыла порт 5173 за 60 с. См. $LOG" >&2
exit 1
