#!/usr/bin/env python3
"""Генерация kb/ui_assistant/generated/ui_catalog_knowledge.scs из knowledge/pack.json.

Файл ТОЛЬКО навешивает nrel_ui_knowledge_text и nrel_ui_knowledge_source на
существующие классы редактора (concept_ui_*). Ни один тип не объявляется.

Запуск:
    python tools/generate_kb_scs.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service" / "src"))

from ostis_ui_assistant.knowledge.render import (  # noqa: E402
    _global_defaults,
    component_type_line,
    property_line,
)

PACK_PATH = ROOT / "knowledge" / "pack.json"
PROVENANCE_PATH = ROOT / "knowledge" / "provenance.json"
OUT_PATH = ROOT / "kb" / "ui_assistant" / "generated" / "ui_catalog_knowledge.scs"

HEADER = """// СГЕНЕРИРОВАНО tools/generate_kb_scs.py из knowledge/pack.json.
// Только навешивание текстов на существующие классы редактора.
// Запрещено объявлять типы (AGENTS.md, 1.5): у классов не должно быть объявлений.
"""


def scs_safe(text: str) -> str:
    """Текст знания — одна строка без квадратных скобок и разделителей."""
    return (
        text.replace("\\", "/")
        .replace("[", "(")
        .replace("]", ")")
        .replace(";;", ";")
        .replace("\n", " ")
        .strip()
    )


def source_text(pack: dict) -> str:
    commit = (pack.get("sources") or {}).get("catalog_commit", "unknown")
    return f"vodo4kin/ostis-ui-editor@{commit}:client/src/model/catalog.ts"


def block(sc_class: str, text: str, source: str) -> str:
    return (
        f"{sc_class}\n"
        f"=> nrel_ui_knowledge_text: [{scs_safe(text)}];\n"
        f"=> nrel_ui_knowledge_source: [{scs_safe(source)}];;\n"
    )


def main() -> int:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    global_defaults = _global_defaults(pack)
    source = source_text(pack)

    parts = [HEADER]
    parts.append("// --- Типы компонентов (16) ---\n")
    for item in pack.get("component_types", []):
        parts.append(block(item["sc_class"], component_type_line(item, global_defaults), source))

    parts.append("\n// --- Свойства (27) ---\n")
    for prop in pack.get("properties", []):
        parts.append(block(prop["sc_class"], property_line(prop), source))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(
        f"записано: {OUT_PATH} "
        f"({len(pack.get('component_types', []))} типов, "
        f"{len(pack.get('properties', []))} свойств)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
