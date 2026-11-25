"""Контракт знаний: коллизии идентификаторов, домен-тексты, сгенерированный .scs."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "kb" / "ui_assistant"
GENERATED = KB / "generated" / "ui_catalog_knowledge.scs"


def test_no_identifier_collisions() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_id_collisions.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_scs_uses_current_relation_spelling() -> None:
    """Наши .scs не должны использовать устаревшее имя типа отношения."""
    files = sorted((*KB.glob("*.scs"), *GENERATED.parent.glob("*.scs")))
    assert files, "тест не нашёл наши .scs"
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "sc_node_norole_relation" not in text, path
    dialog = (KB / "ui_dialog.scs").read_text(encoding="utf-8")
    assert dialog.count("<- sc_node_non_role_relation;;") >= 12


def test_domain_knowledge_complete(pack: dict) -> None:
    assert len(pack["principles"]) == 5
    assert len(pack["methodology_stages"]) >= 10
    assert len(pack["environment_notes"]) >= 4
    for section in ("principles", "methodology_stages", "environment_notes"):
        for item in pack[section]:
            assert item["idtf"], section
            assert len(item["text_ru"]) > 40, item["idtf"]
            assert item["source_ru"], item["idtf"]


def test_generated_scs_attaches_without_declaring(pack: dict) -> None:
    text = GENERATED.read_text(encoding="utf-8")
    assert not re.search(r"<-\s*sc_node_", text), "сгенерированный файл не должен объявлять типы"
    blocks = re.findall(r"nrel_ui_knowledge_text:", text)
    assert len(blocks) == (
        len(pack["component_types"]) + len(pack["properties"]) + len(pack["relations"])
    )
    assert "concept_ui_button" in text
    assert "concept_ui_font_size" in text
    assert "nrel_ui_input_target" in text


def test_generated_texts_match_pack_fallback(pack: dict) -> None:
    """Текст из БЗ и строка из pack.json должны совпадать, иначе режимы разойдутся."""
    from ostis_ui_assistant.knowledge.render import (
        _global_defaults,
        component_type_line,
        property_line,
        relation_line,
    )

    text = GENERATED.read_text(encoding="utf-8")
    for item in pack["component_types"]:
        line = component_type_line(item, _global_defaults(pack))
        assert line in text, item["sc_class"]
    for prop in pack["properties"]:
        assert property_line(prop) in text, prop["sc_class"]
    for relation in pack["relations"]:
        assert relation_line(relation) in text, relation["idtf"]
