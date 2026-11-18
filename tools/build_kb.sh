#!/usr/bin/env bash
# Собирает БЗ из external/ (read-only) и kb/ в .runtime/kb.bin.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SC_BUILDER="$ROOT/.runtime/sc-machine/bin/sc-builder"
if [ ! -x "$SC_BUILDER" ]; then
  echo "ОШИБКА: sc-builder не найден. Выполните: make setup" >&2
  exit 1
fi

PID_FILE="$ROOT/.runtime/sc-machine.pid"
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "ОШИБКА: sc-machine запущена и держит .runtime/kb.bin." >&2
  echo "Остановите её перед пересборкой: make machine-stop" >&2
  exit 1
fi

OUTPUT="${KB_OUTPUT:-$ROOT/.runtime/kb.bin}"
mkdir -p "$ROOT/.runtime" "$ROOT/service/logs"
"$SC_BUILDER" -i "${KB_REPO_PATH:-platform/repo.path}" -o "$OUTPUT" --clear
echo "БЗ собрана: $OUTPUT"
