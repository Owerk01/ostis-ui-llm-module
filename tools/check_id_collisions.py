#!/usr/bin/env python3
"""Контрактная проверка наших .scs.

Проверяет:
1. Наши файлы не объявляют чужие типы (concept_ui_* редактора, nrel_ui_*).
2. Сгенерированный файл вообще ничего не объявляет.
3. Набор объявленных нами классов/отношений совпадает с замороженным списком 3.6.
4. Все существующие классы, к которым цепляются тексты, есть в abstract_ui_model.scs.

Запуск: python tools/check_id_collisions.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service" / "src"))

from ostis_ui_assistant.knowledge.identifiers import (  # noqa: E402
    EXISTING_CLASSES,
    EXISTING_RELATIONS,
    NEW_ACTIONS,
    NEW_CLASSES,
    NEW_RELATIONS,
)

KB_DIR = ROOT / "kb" / "ui_assistant"
GENERATED = KB_DIR / "generated" / "ui_catalog_knowledge.scs"
ABSTRACT_MODEL = ROOT / "external" / "ostis-ui-editor" / "docs" / "abstract_ui_model.scs"

DECL_RE = re.compile(r"^\s*(\w+)\s*<-\s*(sc_node_\w+)\s*;;", re.M)
ANY_CLASS_DECL_RE = re.compile(r"<-\s*sc_node_", re.M)


def scs_files() -> list[Path]:
    return sorted(KB_DIR.rglob("*.scs"))


def declared(path: Path) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in DECL_RE.finditer(path.read_text(encoding="utf-8"))]


def referenced_types(path: Path) -> list[str]:
    """Идентификаторы, к которым файл навешивает знания (первая строка блока)."""
    result: list[str] = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        lines = [line for line in lines if not line.startswith("//")]
        if lines and re.fullmatch(r"\w+", lines[0]) and "nrel_ui_knowledge_text" in block:
            result.append(lines[0])
    return result


def check() -> list[str]:
    errors: list[str] = []
    declared_all: dict[str, Path] = {}

    for path in scs_files():
        for idtf, kind in declared(path):
            declared_all[idtf] = path
            if idtf in EXISTING_CLASSES or idtf in EXISTING_RELATIONS:
                errors.append(f"{path.name}: объявляет чужой идентификатор {idtf} ({kind})")

    if GENERATED.exists() and ANY_CLASS_DECL_RE.search(GENERATED.read_text(encoding="utf-8")):
        errors.append(f"{GENERATED.name}: сгенерированный файл не должен объявлять типы")

    expected = NEW_CLASSES | NEW_RELATIONS | NEW_ACTIONS
    missing = expected - set(declared_all)
    extra = set(declared_all) - expected
    if missing:
        errors.append(f"не объявлены идентификаторы из 3.6: {sorted(missing)}")
    if extra:
        errors.append(f"объявлены идентификаторы вне 3.6: {sorted(extra)}")

    if not ABSTRACT_MODEL.exists():
        errors.append(f"нет схемы редактора: {ABSTRACT_MODEL}")
        return errors

    model_text = ABSTRACT_MODEL.read_text(encoding="utf-8")
    if GENERATED.exists():
        for idtf in referenced_types(GENERATED):
            if idtf not in EXISTING_CLASSES:
                errors.append(f"{GENERATED.name}: текст навешен на чужой класс {idtf}")
            elif not re.search(rf"\b{re.escape(idtf)}\b", model_text):
                errors.append(f"{GENERATED.name}: класса {idtf} нет в abstract_ui_model.scs")

    return errors


def main() -> int:
    errors = check()
    if errors:
        print("ПРОВЕРКА НЕ ПРОЙДЕНА:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(
        f"OK: {len(scs_files())} файлов .scs, "
        f"{len(NEW_CLASSES) + len(NEW_RELATIONS) + len(NEW_ACTIONS)} наших идентификаторов, коллизий нет"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
