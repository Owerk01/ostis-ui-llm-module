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

mkdir -p "$ROOT/.runtime" "$ROOT/service/logs"
"$SC_BUILDER" -i platform/repo.path -o .runtime/kb.bin --clear
echo "БЗ собрана: $ROOT/.runtime/kb.bin"
