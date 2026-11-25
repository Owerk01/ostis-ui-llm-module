"""Контрактные тесты knowledge pack."""

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
    assert len(pack["relations"]) == 6
    assert pack["link_rules"]["action_sources"] == ["button", "select", "menu_item"]


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
        "nrel_ui_input_target",
        "nrel_ui_output_target",
        "nrel_ui_has_component",
        "nrel_ui_id",
        "nrel_ui_value",
    }
    for item in pack["relations"]:
        assert item["meaning_ru"]
    by_kind = {item["kind"]: item for item in pack["relations"]}
    assert by_kind["input_target"]["sources"] == ["button", "select", "menu_item"]
    assert by_kind["input_target"]["targets"] == [
        "text_field",
        "text_area",
        "select",
        "slider",
    ]
    assert len(by_kind["output_target"]["targets"]) == 13
    assert by_kind["contains"]["constraints_ru"]


def test_action_id_only_for_action_sources(pack: dict) -> None:
    """action_id ограничен button/select/menu_item; у остальных 26 свойств."""
    action_sources = set(pack["link_rules"]["action_sources"])
    all_keys = {item["key"] for item in pack["properties"]}
    for item in pack["component_types"]:
        allowed = set(item["allowed_props"])
        if item["type_id"] in action_sources:
            assert allowed == all_keys, item["type_id"]
            assert "action_id" in allowed
        else:
            assert allowed == all_keys - {"action_id"}, item["type_id"]
            assert "action_id" not in allowed


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
    labels = provenance["knowledge_blocks"]["catalog_labels"]
    assert "i18n/ru.ts" in labels["file"]
    assert labels["count"] == len(pack["component_types"])
    assert pack["sources"]["labels"].startswith("client/src/i18n/ru.ts")
