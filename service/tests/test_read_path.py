"""Read-путь не должен создавать элементы в sc-памяти."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = (
    ROOT / "service" / "src" / "ostis_ui_assistant" / "knowledge",
    ROOT / "service" / "src" / "ostis_ui_assistant" / "agents",
)
RESOLVE_RE = re.compile(r"\bScKeynodes\.resolve\s*\(")


def test_read_path_never_resolves_with_type() -> None:
    """Пакеты knowledge/ и agents/ работают на чтение и не создают узлы.

    Пакет sc/ исключён намеренно: он owns запись конструкций диалога и создаёт
    только наши узлы (generate_node / role rrel_N).
    """
    offenders: list[str] = []
    for directory in SCAN_DIRS:
        for path in sorted(directory.rglob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if RESOLVE_RE.search(line):
                    offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert not offenders, "резолв с созданием на read-пути:\n" + "\n".join(offenders)
