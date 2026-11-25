#!/usr/bin/env python3
"""Проверка расхождений между кодом редактора/транслятора и нашими знаниями.

Источник истины — TypeScript-код редактора (`external/ostis-ui-editor`), а не
`docs/catalog.md`. Скрипт читает код только для чтения и сравнивает:

- множества типов, свойств и отношений;
- per-type `allowed_props` (ограничение `action_id`);
- наборы источников/целей `input_target`/`output_target`;
- русские подписи типов из i18n;
- whitelist идентификаторов с keynodes транслятора;
- пины `knowledge/provenance.json` с рабочими копиями `external/`.

`docs/catalog.md` может отставать от кода: это отдельный WARN, а не падение.

Запуск:
    make drift
    python tools/check_upstream_drift.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "external" / "ostis-ui-editor"
TRANSLATOR = ROOT / "external" / "ostis-ui"
PACK_PATH = ROOT / "knowledge" / "pack.json"
PROVENANCE_PATH = ROOT / "knowledge" / "provenance.json"

sys.path.insert(0, str(ROOT / "service" / "src"))
from ostis_ui_assistant.knowledge.identifiers import (  # noqa: E402
    ENVIRONMENT_IDENTIFIERS,
    EXISTING_CLASSES,
    EXISTING_RELATIONS,
)

CATALOG_TS = EDITOR / "client" / "src" / "model" / "catalog.ts"
LINK_RULES_TS = EDITOR / "client" / "src" / "model" / "linkRules.ts"
NAMES_TS = EDITOR / "client" / "src" / "sc" / "names.ts"
TYPES_TS = EDITOR / "client" / "src" / "model" / "types.ts"
I18N_RU = EDITOR / "client" / "src" / "i18n" / "ru.ts"
CATALOG_MD = EDITOR / "docs" / "catalog.md"
KEYNODES_HPP = (
    TRANSLATOR
    / "translators"
    / "HTMLTranslatorModule"
    / "keynodes"
    / "HTMLTranslatorKeynodes.hpp"
)

errors: list[str] = []
warnings: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"не читается {path.relative_to(ROOT)}: {exc}")
        return ""


def ts_map(text: str, name: str) -> dict[str, str]:
    match = re.search(
        rf"export const {name}\b[^=]*=\s*\{{(.*?)\n\}}", text, re.S
    )
    if not match:
        fail(f"{name}: не найден объект в TypeScript")
        return {}
    return {
        key.strip("'\""): value
        for key, value in re.findall(
            r"['\"]?([\w.]+)['\"]?\s*:\s*['\"]([^'\"]+)['\"]", match.group(1)
        )
    }


def ts_array(text: str, name: str) -> list[str]:
    match = re.search(
        rf"export const {name}\b[^=]*=\s*\[(.*?)\]", text, re.S
    )
    if not match:
        fail(f"{name}: не найден массив в TypeScript")
        return []
    return re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))


def ts_union(text: str, name: str) -> list[str]:
    match = re.search(
        rf"export type {name}\s*=\s*(.*?)(?:\n\n|$)", text, re.S
    )
    if not match:
        fail(f"{name}: не найден union-тип в TypeScript")
        return []
    return re.findall(r"'([^']+)'", match.group(1))


def ts_object_keys(text: str, name: str) -> list[str]:
    match = re.search(rf"export type {name}\s*=\s*\{{(.*?)\n\}}", text, re.S)
    if not match:
        fail(f"{name}: не найден тип-объект в TypeScript")
        return []
    return re.findall(r"^\s*(\w+)\s*:", match.group(1), re.M)


def git_info(path: Path) -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", "-C", str(path), *args],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return ""

    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
    }


def catalog_md_labels(text: str) -> dict[str, str]:
    """Колонка «Название» из таблицы `## Типы компонентов`."""
    labels: dict[str, str] = {}
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_table = stripped == "## Типы компонентов"
            continue
        if not in_table or not stripped.startswith("|"):
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if cells and set(cells[0]) <= {"-", ":", " "}:
            continue
        if len(cells) >= 2 and cells[0] not in {"id", ""}:
            labels[cells[0]] = cells[1]
    return labels


def main() -> int:
    catalog = read(CATALOG_TS)
    link_rules = read(LINK_RULES_TS)
    names = read(NAMES_TS)
    types_ts = read(TYPES_TS)
    i18n = read(I18N_RU)
    keynodes = read(KEYNODES_HPP)

    if errors:
        for message in errors:
            print(f"FAIL: {message}")
        return 1

    type_to_class = ts_map(names, "TYPE_TO_CLASS")
    prop_to_class = ts_map(names, "PROP_TO_CLASS")
    rel = ts_map(names, "REL")
    interface_class = re.search(
        r"export const CLASS_INTERFACE\s*=\s*'([^']+)'", names
    )
    if not interface_class:
        fail("CLASS_INTERFACE не найден в names.ts")

    component_types = set(ts_union(types_ts, "ComponentTypeId"))
    property_keys = set(ts_object_keys(types_ts, "ComponentProps"))
    link_kinds = set(ts_union(types_ts, "LinkKindId"))
    action_sources = ts_array(link_rules, "ACTION_LINK_SOURCES")
    input_targets = ts_array(link_rules, "INPUT_TARGET_TYPES")
    output_targets = ts_array(link_rules, "OUTPUT_TARGET_TYPES")

    catalog_types = re.findall(r"entry\(\s*'([^']+)'", catalog.split("COMPONENT_CATALOG", 1)[-1])
    if not catalog_types:
        fail("COMPONENT_CATALOG: не найдены типы в catalog.ts")

    labels: dict[str, str] = {}
    for type_id, label in re.findall(r"'type\.([\w]+)':\s*'([^']+)'", i18n):
        labels[type_id] = label

    translator_idtfs = set(re.findall(r"ScKeynode const (\w+)\{", keynodes))
    if not translator_idtfs:
        fail("не найдены keynodes транслятора")

    # --- Множества типов/свойств/отношений ---------------------------------
    expected_classes = set(type_to_class.values()) | set(prop_to_class.values())
    if interface_class:
        expected_classes.add(interface_class.group(1))
    expected_relations = set(rel.values())

    if component_types != set(type_to_class):
        fail(
            "ComponentTypeId и TYPE_TO_CLASS расходятся: "
            f"{sorted(component_types ^ set(type_to_class))}"
        )
    if set(catalog_types) != component_types:
        fail(
            "COMPONENT_CATALOG и ComponentTypeId расходятся: "
            f"{sorted(set(catalog_types) ^ component_types)}"
        )
    if property_keys != set(prop_to_class):
        fail(
            "ComponentProps и PROP_TO_CLASS расходятся: "
            f"{sorted(property_keys ^ set(prop_to_class))}"
        )
    if set(link_kinds) != {"contains", "input_target", "output_target"}:
        fail(f"LinkKindId неожиданный: {sorted(link_kinds)}")
    if set(link_kinds) - set(rel):
        fail(f"REL не покрывает LinkKindId: {sorted(set(link_kinds) - set(rel))}")

    # --- Pack ---------------------------------------------------------------
    try:
        pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: не читается knowledge/pack.json: {exc}")
        return 1

    pack_types = {item["type_id"]: item for item in pack.get("component_types", [])}
    pack_props = {item["key"] for item in pack.get("properties", [])}
    pack_relations = {item["idtf"]: item for item in pack.get("relations", [])}

    if set(pack_types) != component_types:
        fail(f"pack.component_types расходится с кодом: {sorted(set(pack_types) ^ component_types)}")
    if pack_props != property_keys:
        fail(f"pack.properties расходится с кодом: {sorted(pack_props ^ property_keys)}")
    if set(pack_relations) != expected_relations:
        fail(
            f"pack.relations расходится с names.ts: "
            f"{sorted(set(pack_relations) ^ expected_relations)}"
        )

    for type_id, item in pack_types.items():
        expected = property_keys if type_id in action_sources else property_keys - {"action_id"}
        actual = set(item.get("allowed_props", []))
        if actual != expected:
            fail(
                f"allowed_props[{type_id}] расходятся: "
                f"лишние {sorted(actual - expected)}, нет {sorted(expected - actual)}"
            )

    expected_link_rules = {
        "action_sources": action_sources,
        "input_targets": input_targets,
        "output_targets": output_targets,
    }
    for key, expected in expected_link_rules.items():
        actual = pack.get("link_rules", {}).get(key, [])
        if list(actual) != list(expected):
            fail(f"pack.link_rules.{key} расходится с linkRules.ts: {actual} != {expected}")

    for kind, expected_targets in (
        ("input_target", input_targets),
        ("output_target", output_targets),
    ):
        item = next(
            (value for value in pack_relations.values() if value.get("kind") == kind),
            None,
        )
        if item is None:
            fail(f"в pack нет отношения kind={kind}")
            continue
        if list(item.get("sources", [])) != action_sources:
            fail(f"{item['idtf']}: sources расходятся с ACTION_LINK_SOURCES")
        if list(item.get("targets", [])) != expected_targets:
            fail(f"{item['idtf']}: targets расходятся с linkRules.ts")
    contains = next(
        (value for value in pack_relations.values() if value.get("kind") == "contains"),
        None,
    )
    if contains is None or not contains.get("constraints_ru"):
        fail("nrel_ui_contains должен быть помечен как отношение без ограничений по типам")

    for type_id, item in pack_types.items():
        expected_label = labels.get(type_id)
        if expected_label and item.get("label_ru") != expected_label:
            fail(
                f"label_ru[{type_id}]='{item.get('label_ru')}' "
                f"не совпадает с i18n '{expected_label}'"
            )

    # --- Whitelist против upstream -----------------------------------------
    missing_classes = EXISTING_CLASSES - expected_classes - translator_idtfs
    if missing_classes:
        fail(f"EXISTING_CLASSES отсутствуют upstream: {sorted(missing_classes)}")
    missing_relations = {
        idtf
        for idtf in EXISTING_RELATIONS
        if idtf.startswith("nrel_ui_") and idtf not in expected_relations
    }
    if missing_relations:
        fail(f"EXISTING_RELATIONS отсутствуют в names.ts: {sorted(missing_relations)}")
    missing_environment = ENVIRONMENT_IDENTIFIERS - translator_idtfs
    if missing_environment:
        fail(f"ENVIRONMENT_IDENTIFIERS отсутствуют в keynodes: {sorted(missing_environment)}")

    # --- Пины provenance ----------------------------------------------------
    try:
        provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"не читается knowledge/provenance.json: {exc}")
        provenance = {}

    for name, entry in provenance.get("repositories", {}).items():
        path = ROOT / entry.get("path", "")
        if not path.exists():
            fail(f"provenance[{name}]: нет рабочей копии {entry.get('path')}")
            continue
        info = git_info(path)
        if entry.get("commit") != info["commit"]:
            fail(
                f"provenance[{name}].commit={entry.get('commit')} "
                f"!= HEAD {info['commit']}"
            )
        if entry.get("branch") != info["branch"]:
            fail(
                f"provenance[{name}].branch={entry.get('branch')} "
                f"!= HEAD {info['branch']}"
            )

    catalog_commit = pack.get("sources", {}).get("catalog_commit")
    for block in ("catalog_types", "catalog_properties", "catalog_relations", "catalog_labels"):
        block_commit = provenance.get("knowledge_blocks", {}).get(block, {}).get("commit")
        if block_commit != catalog_commit:
            fail(f"provenance.{block}.commit={block_commit} != pack {catalog_commit}")

    # --- WARN: docs/catalog.md отстаёт от кода ------------------------------
    catalog_md = read(CATALOG_MD)
    if "Одинаковый набор ключей у всех типов" in catalog_md and action_sources:
        warn(
            "docs/catalog.md утверждает «Одинаковый набор ключей у всех типов», "
            f"а catalog.ts ограничивает action_id типами {', '.join(action_sources)}; "
            "сообщить Георгию"
        )
    md_labels = catalog_md_labels(catalog_md)
    if md_labels and set(md_labels) != component_types:
        warn(
            "список типов в docs/catalog.md расходится с кодом: "
            f"{sorted(set(md_labels) ^ component_types)}"
        )
    label_diff = {
        type_id: (md_labels.get(type_id), labels.get(type_id))
        for type_id in component_types
        if type_id in md_labels and md_labels[type_id] != labels.get(type_id)
    }
    if label_diff:
        warn(f"подписи типов в docs/catalog.md расходятся с i18n: {label_diff}")

    for message in warnings:
        print(f"WARN: {message}")
    if errors:
        for message in errors:
            print(f"FAIL: {message}")
        return 1

    print(
        "DRIFT OK: "
        f"{len(component_types)} типов, {len(property_keys)} свойств, "
        f"{len(pack_relations)} отношений, "
        f"allowed_props у {len(pack_types)} типов; "
        f"pins {len(provenance.get('repositories', {}))} репозиториев"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
