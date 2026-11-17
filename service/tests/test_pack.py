"""Контрактные тесты knowledge pack (M1-T2)."""

from __future__ import annotations

import json
from pathlib import Path

from ostis_ui_assistant.knowledge.identifiers import (
    EXISTING_CLASSES,
    PROPERTY_KEYS,
)

ROOT = Path(__file__).resolve().parents[2]


def test_pack_has_expected_counts(pack: dict) -> None:
    assert len(pack["component_types"]) == 16
    assert len(pack["properties"]) == 27
    assert len(pack["relations"]) == 4


def test_pack_is_not_degraded_and_has_provenance(pack: dict) -> None:
    assert pack["degraded"] is False
    assert pack["pack_version"]
    assert pack["sources"]["catalog_commit"]
    assert pack["sources"]["catalog_commit"] != "unknown"


def test_every_type_has_class_label_purpose_and_defaults(pack: dict) -> None:
    type_ids = set()
    for item in pack["component_types"]:
        assert item["type_id"] not in type_ids
        type_ids.add(item["type_id"])
        assert item["sc_class"] in EXISTING_CLASSES
        assert item["sc_class"].startswith("concept_ui_")
        assert item["label_ru"]
        assert item["purpose_ru"]
        assert item["defaults"], item["type_id"]


def test_every_property_has_class_type_meaning(pack: dict) -> None:
    keys = set()
    for item in pack["properties"]:
        assert item["key"] not in keys
        keys.add(item["key"])
        assert item["sc_class"] == f"concept_ui_{item['key']}"
        assert item["type"] in {"string", "number", "boolean", "color", "enum"}
        assert item["meaning_ru"]
    assert keys == PROPERTY_KEYS


def test_relations_match_contract(pack: dict) -> None:
    assert {item["idtf"] for item in pack["relations"]} == {
        "nrel_ui_contains",
        "nrel_ui_has_component",
        "nrel_ui_id",
        "nrel_ui_value",
    }
    for item in pack["relations"]:
        assert item["meaning_ru"]


def test_values_of_properties_fit_declared_types(pack: dict) -> None:
    for item in pack["properties"]:
        default = item["default"]
        if default is None:
            continue
        expected = item["type"]
        if expected == "number":
            assert isinstance(default, (int, float)) and not isinstance(default, bool), item["key"]
        elif expected == "boolean":
            assert isinstance(default, bool), item["key"]
        elif expected in {"string", "color", "enum"}:
            assert isinstance(default, str), item["key"]


def test_provenance_matches_pack(pack: dict) -> None:
    provenance = json.loads(
        (ROOT / "knowledge" / "provenance.json").read_text(encoding="utf-8")
    )
    block = provenance["knowledge_blocks"]["catalog_types"]
    assert block["commit"] == pack["sources"]["catalog_commit"]
    assert block["count"] == len(pack["component_types"])
    assert block["degraded"] is False
