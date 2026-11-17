#!/usr/bin/env bash
# Загружает официальные бинарники sc-machine в .runtime/ (без Docker и без sudo).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SC_MACHINE_VERSION="${SC_MACHINE_VERSION:-0.10.5}"
DEST="$ROOT/.runtime/sc-machine"

case "$(uname -s)" in
  Linux)  OS="Linux" ;;
  Darwin) OS="Darwin" ;;
  *) echo "ОШИБКА: неподдерживаемая ОС $(uname -s)" >&2; exit 1 ;;
esac

ARCH="$(uname -m)"
if [ "$ARCH" != "x86_64" ] && [ "$ARCH" != "amd64" ]; then
  echo "ОШИБКА: для $ARCH нет официальной сборки sc-machine; нужна x86_64" >&2
  exit 1
fi

if [ -x "$DEST/bin/sc-machine" ] && [ -x "$DEST/bin/sc-builder" ]; then
  echo "sc-machine уже установлена: $("$DEST/bin/sc-machine" --version 2>/dev/null || echo "$DEST")"
  exit 0
fi

ARCHIVE="sc-machine-${SC_MACHINE_VERSION}-${OS}.tar.gz"
URL="https://github.com/ostis-ai/sc-machine/releases/download/${SC_MACHINE_VERSION}/${ARCHIVE}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Загрузка $URL"
curl -fsSL --retry 3 -o "$TMP/$ARCHIVE" "$URL"

mkdir -p "$DEST"
tar -xzf "$TMP/$ARCHIVE" -C "$DEST" --strip-components=1
rm -rf "$DEST/include"

echo "Готово: $("$DEST/bin/sc-machine" --version)"
