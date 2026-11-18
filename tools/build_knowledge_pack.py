#!/usr/bin/env python3
"""Сборка knowledge pack из репозитория редактора (M1-T2).

Основной путь: `npx tsx tools/dump_catalog.ts` импортирует catalog.ts/names.ts
и печатает точный JSON. Резервный путь: разбор docs/catalog.md (без defaults
типов, provenance помечается degraded=true).

Запуск:
    python tools/build_knowledge_pack.py
    python tools/build_knowledge_pack.py --dump /tmp/catalog.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EDITOR = ROOT / "external" / "ostis-ui-editor"
CATALOG_TS = EDITOR / "client" / "src" / "model" / "catalog.ts"
NAMES_TS = EDITOR / "client" / "src" / "sc" / "names.ts"
CATALOG_MD = EDITOR / "docs" / "catalog.md"
OVERRIDES_PATH = ROOT / "knowledge" / "purpose_overrides.json"
PACK_PATH = ROOT / "knowledge" / "pack.json"
PROVENANCE_PATH = ROOT / "knowledge" / "provenance.json"

KNOWLEDGE_DIR = ROOT / "kb" / "ui_assistant"
DOMAIN_FILES = {
    "principles": ("ui_principles.scs", "concept_ui_development_principle"),
    "methodology_stages": ("ui_methodology.scs", None),
    "environment_notes": ("ui_environment.scs", "concept_ui_environment_note"),
}

RELATION_KINDS = {
    "nrel_ui_contains": "contains",
    "nrel_ui_has_component": "has_component",
    "nrel_ui_id": "id",
    "nrel_ui_value": "value",
}


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_commit(path: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def parse_knowledge_scs(path: Path) -> list[dict[str, str]]:
    """Разбирает наши .scs с одним знанием на блок (блоки разделены пустой строкой).

    Ожидаемая форма блока (AGENTS.md, 3.6):
        <idtf>
        <- <class>;
        => nrel_main_idtf: [<title>] (* <- lang_ru;; *);
        => nrel_ui_knowledge_text: [<text>];
        => nrel_ui_knowledge_source: [<source>];;
    Текст знания — одна строка в квадратных скобках, без вложенных скобок.
    """
    if not path.exists():
        return []

    text_re = re.compile(r"nrel_ui_knowledge_text:\s*\[(.+?)\]", re.S)
    source_re = re.compile(r"nrel_ui_knowledge_source:\s*\[(.+?)\]", re.S)
    title_re = re.compile(r"nrel_main_idtf:\s*\[(.+?)\]", re.S)
    class_re = re.compile(r"<-\s*(\w+)\s*;")

    items: list[dict[str, str]] = []
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8"))
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        lines = [line for line in lines if not line.startswith("//")]
        if len(lines) < 2:
            continue
        idtf = lines[0]
        if not re.fullmatch(r"\w+", idtf):
            continue
        class_match = class_re.search(block)
        text_match = text_re.search(block)
        if not class_match or not text_match:
            continue
        title_match = title_re.search(block)
        source_match = source_re.search(block)
        items.append(
            {
                "idtf": idtf,
                "class": class_match.group(1),
                "title_ru": title_match.group(1).strip() if title_match else idtf,
                "text_ru": " ".join(text_match.group(1).split()),
                "source_ru": " ".join(source_match.group(1).split())
                if source_match
                else "",
                "file": path.name,
            }
        )
    return items


def load_domain_knowledge() -> tuple[dict[str, list[dict[str, str]]], dict[str, int]]:
    """Собирает принципы, методику и сведения о среде из наших .scs."""
    result: dict[str, list[dict[str, str]]] = {}
    counts: dict[str, int] = {}

    for section, (filename, class_filter) in DOMAIN_FILES.items():
        items = parse_knowledge_scs(KNOWLEDGE_DIR / filename)
        if class_filter is not None:
            items = [item for item in items if item["class"] == class_filter]
        elif filename == "ui_methodology.scs":
            # Процессы методики (<- concept_ui_knowledge) идут перед этапами.
            order = {"concept_ui_knowledge": 0, "concept_ui_development_stage": 1}
            items.sort(key=lambda item: order.get(item["class"], 2))
        for item in items:
            item.pop("class", None)
            item.pop("file", None)
        result[section] = items
        counts[section] = len(items)
    return result, counts


def run_ts_dump() -> dict[str, Any]:
    command = ["npx", "--yes", "tsx", "tools/dump_catalog.ts"]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"npx tsx завершился с кодом {result.returncode}: {result.stderr[-1000:]}")
    return json.loads(result.stdout)


def _md_tables(text: str, heading: str) -> list[list[str]]:
    """Возвращает все строки markdown-таблиц после указанного заголовка."""
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return []

    rows: list[list[str]] = []
    in_table = False
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("## "):
            break
        if not stripped.startswith("|"):
            if in_table and stripped:
                break
            continue
        if set(stripped) <= {"|", "-", ":", " "}:
            continue
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if cells and cells[0].lower() not in {"id", "ключ", "свойство", "что"}:
            rows.append(cells)
            in_table = True
    return rows


def parse_catalog_md() -> dict[str, Any]:
    """Резервный путь: только имена, классы и ярлыки из docs/catalog.md."""
    text = CATALOG_MD.read_text(encoding="utf-8")

    labels = {row[0]: row[1] for row in _md_tables(text, "## Типы компонентов") if len(row) >= 2}
    type_classes = {
        row[0]: row[1] for row in _md_tables(text, "### Типы компонентов") if len(row) >= 2
    }
    prop_classes = {
        row[0]: row[1] for row in _md_tables(text, "### Свойства") if len(row) >= 2
    }

    types = [
        {
            "type_id": type_id,
            "label_ru": label,
            "preview": "rect",
            "sc_class": type_classes.get(type_id),
            "defaults": {},
        }
        for type_id, label in labels.items()
        if type_id in type_classes
    ]
    properties = [
        {"key": key, "sc_class": sc_class} for key, sc_class in prop_classes.items()
    ]
    relations = [
        {"kind": kind, "idtf": idtf} for idtf, kind in RELATION_KINDS.items()
    ]
    return {
        "class_interface": "concept_ui_interface",
        "types": types,
        "properties": properties,
        "relations": relations,
    }


def build_pack(
    dump: dict[str, Any],
    overrides: dict[str, Any],
    degraded: bool,
    domain: dict[str, list[dict[str, str]]] | None = None,
) -> dict[str, Any]:
    domain = domain or {"principles": [], "methodology_stages": [], "environment_notes": []}
    generated_at = iso_now()
    type_overrides = overrides.get("types", {})
    prop_overrides = overrides.get("properties", {})
    relation_meanings = overrides.get("relations", {})

    component_types: list[dict[str, Any]] = []
    for item in dump["types"]:
        type_id = item["type_id"]
        purpose = type_overrides.get(type_id, {}).get("purpose_ru", "")
        component_types.append(
            {
                "type_id": type_id,
                "sc_class": item["sc_class"],
                "label_ru": item["label_ru"],
                "purpose_ru": purpose,
                "defaults": item.get("defaults", {}),
            }
        )

    properties: list[dict[str, Any]] = []
    for item in dump["properties"]:
        key = item["key"]
        override = prop_overrides.get(key, {})
        record: dict[str, Any] = {
            "key": key,
            "sc_class": item["sc_class"],
            "type": override.get("type", "string"),
            "default": override.get("default"),
            "meaning_ru": override.get("meaning_ru", ""),
        }
        if override.get("default_note_ru"):
            record["default_note_ru"] = override["default_note_ru"]
        if "allowed_values" in override:
            record["allowed_values"] = override["allowed_values"]
        properties.append(record)

    relations = [
        {
            "idtf": item["idtf"],
            "kind": item.get("kind", RELATION_KINDS.get(item["idtf"], "")),
            "meaning_ru": relation_meanings.get(item["idtf"], ""),
        }
        for item in dump["relations"]
    ]

    return {
        "pack_version": generated_at,
        "prompt_version": "v1",
        "generated_at": generated_at,
        "degraded": degraded,
        "sources": {
            "catalog": "external/ostis-ui-editor",
            "catalog_commit": git_commit(EDITOR),
            "primary": "client/src/model/catalog.ts + client/src/sc/names.ts",
            "fallback": "docs/catalog.md" if degraded else None,
        },
        "component_types": component_types,
        "properties": properties,
        "relations": relations,
        "principles": domain["principles"],
        "methodology_stages": domain["methodology_stages"],
        "environment_notes": domain["environment_notes"],
    }


def update_provenance(pack: dict[str, Any], degraded: bool) -> None:
    if PROVENANCE_PATH.exists():
        provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    else:
        provenance = {"schema_version": 1, "repositories": {}}

    commit = git_commit(EDITOR)
    extracted_at = pack["pack_version"]
    source_file = (
        "docs/catalog.md"
        if degraded
        else "client/src/model/catalog.ts; client/src/sc/names.ts; client/src/model/propSets.ts"
    )
    provenance["generated_at"] = extracted_at
    provenance["knowledge_blocks"] = {
        "catalog_types": {
            "repo": "https://github.com/vodo4kin/ostis-ui-editor",
            "commit": commit,
            "file": source_file,
            "extracted_at": extracted_at,
            "degraded": degraded,
            "count": len(pack["component_types"]),
        },
        "catalog_properties": {
            "repo": "https://github.com/vodo4kin/ostis-ui-editor",
            "commit": commit,
            "file": source_file,
            "extracted_at": extracted_at,
            "degraded": degraded,
            "count": len(pack["properties"]),
        },
        "catalog_relations": {
            "repo": "https://github.com/vodo4kin/ostis-ui-editor",
            "commit": commit,
            "file": source_file,
            "extracted_at": extracted_at,
            "degraded": degraded,
            "count": len(pack["relations"]),
        },
    }

    domain_sources = {
        "principles": ("ui_principles.scs", "Проект инструментальной среды, раздел 5"),
        "methodology_stages": ("ui_methodology.scs", "Проект инструментальной среды, раздел 4"),
        "environment_notes": ("ui_environment.scs", "Проект инструментальной среды, раздел 7"),
    }
    for block, (filename, source) in domain_sources.items():
        provenance["knowledge_blocks"][block] = {
            "repo": "local:ostis-ui-assistant",
            "commit": None,
            "file": f"kb/ui_assistant/{filename}",
            "source": source,
            "extracted_at": extracted_at,
            "degraded": False,
            "count": len(pack.get(block, [])),
        }
    PROVENANCE_PATH.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Сборка knowledge/pack.json")
    parser.add_argument("--dump", type=Path, help="готовый JSON от tools/dump_catalog.ts")
    parser.add_argument(
        "--no-npx",
        action="store_true",
        help="не запускать npx, сразу разбирать docs/catalog.md",
    )
    args = parser.parse_args()

    overrides = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
    domain, domain_counts = load_domain_knowledge()
    if not all(domain_counts.values()):
        print(f"WARN: неполные domain-знания: {domain_counts}", file=sys.stderr)
    degraded = False

    if args.dump:
        dump = json.loads(args.dump.read_text(encoding="utf-8"))
    elif not args.no_npx:
        try:
            dump = run_ts_dump()
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            print(f"WARN: основной путь сборки недоступен: {exc}", file=sys.stderr)
            print("WARN: перехожу на docs/catalog.md, defaults типов будут пустыми", file=sys.stderr)
            dump = parse_catalog_md()
            degraded = True
    else:
        dump = parse_catalog_md()
        degraded = True

    pack = build_pack(dump, overrides, degraded, domain=domain)
    PACK_PATH.write_text(
        json.dumps(pack, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    update_provenance(pack, degraded)

    print(
        f"pack: {len(pack['component_types'])} типов, "
        f"{len(pack['properties'])} свойств, {len(pack['relations'])} отношений, "
        f"{len(pack['principles'])} принципов, "
        f"{len(pack['methodology_stages'])} этапов, "
        f"{len(pack['environment_notes'])} сведений о среде"
    )
    print(f"pack_version: {pack['pack_version']} (degraded={degraded})")
    print(f"записано: {PACK_PATH}")
    if degraded:
        print("WARN: defaults типов отсутствуют (fallback по catalog.md)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
