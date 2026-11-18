"""Чтение знаний о разработке ПИ из sc-памяти.

Основной источник — БЗ. Локальный pack.json используется как per-item fallback:
если у класса нет текста в БЗ, остаётся запись из pack и выставляется kb_partial.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any

from sc_client import client
from sc_client.client import search_by_template
from sc_client.constants import sc_type
from sc_client.models import ScTemplate
from sc_kpm import ScKeynodes
from sc_kpm.utils import get_element_system_identifier, get_link_content_data

logger = logging.getLogger(__name__)

TEXT_REL = "nrel_ui_knowledge_text"
SOURCE_REL = "nrel_ui_knowledge_source"

PRINCIPLE_CLASS = "concept_ui_development_principle"
STAGE_CLASS = "concept_ui_development_stage"
ENVIRONMENT_CLASS = "concept_ui_environment_note"
KNOWLEDGE_CLASS = "concept_ui_knowledge"

SECTION_CLASSES = {
    "principles": PRINCIPLE_CLASS,
    "methodology_stages": STAGE_CLASS,
    "environment_notes": ENVIRONMENT_CLASS,
}


@dataclass
class KbStatus:
    connected: bool = False
    partial: bool = False
    source: str = "fallback"
    missing: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "partial": self.partial,
            "source": self.source,
            "missing": self.missing,
            "errors": self.errors,
            "counts": self.counts,
        }


def _connect(url: str) -> bool:
    if not client.is_connected():
        try:
            client.connect(url)
        except Exception as exc:  # noqa: BLE001 - причина уходит в /health и журнал
            logger.warning("Не удалось подключиться к БЗ %s: %s", url, exc)
            return False
    return bool(client.is_connected())


def _text(node, rel_idtf: str) -> str | None:
    templ = ScTemplate()
    templ.quintuple(
        node,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE_LINK >> "_link",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes[rel_idtf],
    )
    results = search_by_template(templ)
    if not results:
        return None
    value = get_link_content_data(results[0].get("_link"))
    text = str(value).strip()
    return text or None


def _class_text(sc_class: str) -> str | None:
    addr = ScKeynodes.resolve(sc_class, sc_type.CONST_NODE_CLASS)
    if not addr.is_valid():
        return None
    return _text(addr, TEXT_REL)


def _instances(class_idtf: str) -> list[Any]:
    templ = ScTemplate()
    templ.triple(
        ScKeynodes[class_idtf],
        sc_type.VAR_PERM_POS_ARC,
        sc_type.VAR_NODE >> "_item",
    )
    return [row.get("_item") for row in search_by_template(templ)]


def _read_items(class_idtf: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for addr in _instances(class_idtf):
        idtf = get_element_system_identifier(addr) or ""
        text = _text(addr, TEXT_REL)
        source = _text(addr, SOURCE_REL) or ""
        title = _title(addr) or idtf
        items.append(
            {
                "idtf": idtf,
                "title_ru": title,
                "text_ru": text or "",
                "source_ru": source,
            }
        )
    return [item for item in items if item["idtf"]]


def _title(node) -> str | None:
    templ = ScTemplate()
    templ.quintuple(
        node,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE_LINK >> "_link",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes["nrel_main_idtf"],
    )
    results = search_by_template(templ)
    if not results:
        return None
    return str(get_link_content_data(results[0].get("_link"))).strip() or None


def _merge_section(
    kb_items: list[dict[str, str]],
    pack_items: list[dict[str, Any]],
    missing: list[str],
) -> list[dict[str, Any]]:
    """Накладывает тексты БЗ на pack; недостающие узлы добирает из pack."""
    pack_by_id = {item["idtf"]: item for item in pack_items}
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for kb_item in kb_items:
        idtf = kb_item["idtf"]
        seen.add(idtf)
        base = dict(pack_by_id.get(idtf, {"idtf": idtf}))
        base["title_ru"] = kb_item.get("title_ru") or base.get("title_ru", idtf)
        if kb_item.get("text_ru"):
            base["text_ru"] = kb_item["text_ru"]
        else:
            missing.append(idtf)
        if kb_item.get("source_ru"):
            base["source_ru"] = kb_item["source_ru"]
        merged.append(base)

    for pack_item in pack_items:
        if pack_item["idtf"] not in seen:
            missing.append(pack_item["idtf"])
            merged.append(dict(pack_item))

    return merged


def load_pack_from_kb(
    pack: dict[str, Any],
    ws_url: str,
    *,
    allow_fallback: bool = True,
) -> tuple[dict[str, Any], KbStatus]:
    """Возвращает копию pack с текстами из БЗ и статус источника знаний."""
    status = KbStatus()

    if not _connect(ws_url):
        status.errors.append("sc-memory недоступна")
        if not allow_fallback:
            raise RuntimeError("sc-memory недоступна, а fallback запрещён (KB_FALLBACK_ALLOWED=false)")
        logger.warning("БЗ недоступна: работаю на knowledge/pack.json (fallback)")
        return copy.deepcopy(pack), status

    status.connected = True
    result = copy.deepcopy(pack)
    missing: list[str] = []

    try:
        for item in result.get("component_types", []):
            text = _class_text(item["sc_class"])
            if text:
                item["kb_text"] = text
            else:
                missing.append(item["sc_class"])

        for item in result.get("properties", []):
            text = _class_text(item["sc_class"])
            if text:
                item["kb_text"] = text
            else:
                missing.append(item["sc_class"])

        processes = _read_items(KNOWLEDGE_CLASS)
        stages = _read_items(STAGE_CLASS)
        result["principles"] = _merge_section(
            _read_items(PRINCIPLE_CLASS), result.get("principles", []), missing
        )
        result["methodology_stages"] = _merge_section(
            processes + stages, result.get("methodology_stages", []), missing
        )
        result["environment_notes"] = _merge_section(
            _read_items(ENVIRONMENT_CLASS), result.get("environment_notes", []), missing
        )
    except Exception as exc:  # noqa: BLE001 - не повреждаем БЗ, деградируем в pack
        status.errors.append(str(exc))
        status.source = "fallback"
        status.connected = False
        logger.warning("Ошибка чтения БЗ, работаю на pack.json: %s", exc)
        if not allow_fallback:
            raise
        return copy.deepcopy(pack), status

    status.missing = sorted(set(missing))
    status.partial = bool(status.missing)
    status.source = "kb"
    status.counts = {
        "component_types": len(result.get("component_types", [])),
        "properties": len(result.get("properties", [])),
        "principles": len(result.get("principles", [])),
        "methodology_stages": len(result.get("methodology_stages", [])),
        "environment_notes": len(result.get("environment_notes", [])),
    }

    if status.partial:
        logger.warning("БЗ прочитана частично, fallback для %s узлов", len(status.missing))
    else:
        logger.info(
            "Знания загружены из БЗ: %s типов, %s свойств, %s принципов, %s этапов",
            status.counts["component_types"],
            status.counts["properties"],
            status.counts["principles"],
            status.counts["methodology_stages"],
        )
    return result, status


def close() -> None:
    """Закрывает общее соединение py-sc-client, если оно открыто."""
    if client.is_connected():
        client.disconnect()
