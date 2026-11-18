"""Конструкции диалога в sc-памяти."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sc_client.client import search_by_template
from sc_client.constants import sc_type
from sc_client.models import ScAddr, ScTemplate
from sc_kpm import ScKeynodes
from sc_kpm.utils import (
    generate_binary_relation,
    generate_connector,
    generate_link,
    generate_node,
    get_element_system_identifier,
    get_link_content_data,
)

from ..knowledge.identifiers import NEW_CLASSES
from . import keynodes as kn

logger = logging.getLogger(__name__)


def _rrel(index: int) -> ScAddr:
    """rrel_1..rrel_10 штатные, дальше создаём одноимённые узлы роли сами."""
    if 1 <= index <= 10:
        return ScKeynodes.rrel_index(index)
    return ScKeynodes.resolve(f"rrel_{index}", sc_type.CONST_NODE_ROLE)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_dialog() -> ScAddr:
    dialog = generate_node(sc_type.CONST_NODE)
    generate_connector(sc_type.CONST_PERM_POS_ARC, ScKeynodes["concept_ui_dialog"], dialog)
    return dialog


def ensure_dialog(dialog: ScAddr | None) -> ScAddr:
    if dialog is not None and dialog.is_valid():
        return dialog
    return create_dialog()


def _message_index(dialog: ScAddr) -> int:
    templ = ScTemplate()
    templ.quintuple(
        dialog,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE >> "_message",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes["nrel_ui_dialog_message"],
    )
    return len(search_by_template(templ)) + 1


def _append_message(
    dialog: ScAddr,
    text: str,
    role_class: str,
    state: str,
    *,
    model: str | None = None,
    prompt_version: str | None = None,
    sources: list[ScAddr] | None = None,
    knowledge_source: str | None = None,
) -> ScAddr:
    message = generate_node(sc_type.CONST_NODE)
    generate_connector(sc_type.CONST_PERM_POS_ARC, ScKeynodes[role_class], message)

    text_link = generate_link(text)
    generate_binary_relation(
        sc_type.CONST_COMMON_ARC, message, text_link, ScKeynodes["nrel_ui_value"]
    )

    time_link = generate_link(_now_iso())
    generate_binary_relation(
        sc_type.CONST_COMMON_ARC, message, time_link, ScKeynodes["nrel_ui_message_time"]
    )

    state_link = generate_link(state)
    generate_binary_relation(
        sc_type.CONST_COMMON_ARC, message, state_link, ScKeynodes["nrel_ui_message_state"]
    )

    if model:
        model_link = generate_link(model)
        generate_binary_relation(
            sc_type.CONST_COMMON_ARC, message, model_link, ScKeynodes["nrel_ui_llm_model"]
        )
    if prompt_version:
        version_link = generate_link(prompt_version)
        generate_binary_relation(
            sc_type.CONST_COMMON_ARC,
            message,
            version_link,
            ScKeynodes["nrel_ui_prompt_version"],
        )
    if knowledge_source:
        source_link = generate_link(knowledge_source)
        generate_binary_relation(
            sc_type.CONST_COMMON_ARC,
            message,
            source_link,
            ScKeynodes["nrel_ui_knowledge_source"],
        )
    for source in sources or []:
        if source.is_valid():
            generate_binary_relation(
                sc_type.CONST_COMMON_ARC, message, source, ScKeynodes["nrel_ui_answer_source"]
            )

    generate_binary_relation(
        sc_type.CONST_COMMON_ARC,
        dialog,
        message,
        ScKeynodes["nrel_ui_dialog_message"],
        _rrel(_message_index(dialog)),
    )
    return message


def append_user_message(dialog: ScAddr, text: str) -> ScAddr:
    return _append_message(dialog, text, "concept_ui_user_message", kn.STATUS_DONE)


def append_assistant_message(
    dialog: ScAddr,
    text: str,
    model: str,
    prompt_version: str,
    sources: list[ScAddr] | None = None,
    state: str = kn.STATUS_DONE,
    knowledge_source: str = "unknown",
) -> ScAddr:
    return _append_message(
        dialog,
        text,
        "concept_ui_assistant_message",
        state,
        model=model,
        prompt_version=prompt_version,
        sources=sources,
        knowledge_source=knowledge_source,
    )


def append_error_message(dialog: ScAddr, reason: str) -> ScAddr:
    return _append_message(
        dialog,
        reason,
        "concept_ui_assistant_message",
        kn.STATUS_ERROR,
        knowledge_source="unknown",
    )


def read_state(message: ScAddr) -> str | None:
    templ = ScTemplate()
    templ.quintuple(
        message,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE_LINK >> "_link",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes["nrel_ui_message_state"],
    )
    rows = search_by_template(templ)
    return str(get_link_content_data(rows[0].get("_link"))) if rows else None


def _link_value(message: ScAddr, relation: str) -> str | None:
    templ = ScTemplate()
    templ.quintuple(
        message,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE_LINK >> "_link",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes[relation],
    )
    rows = search_by_template(templ)
    if not rows:
        return None
    return str(get_link_content_data(rows[0].get("_link")))


def _role(message: ScAddr) -> str:
    for class_idtf, role in (
        ("concept_ui_user_message", "user"),
        ("concept_ui_assistant_message", "assistant"),
    ):
        templ = ScTemplate()
        templ.triple(ScKeynodes[class_idtf], sc_type.VAR_PERM_POS_ARC, message)
        if search_by_template(templ):
            return role
    return "assistant"


def _sources(message: ScAddr) -> list[dict[str, str]]:
    templ = ScTemplate()
    templ.quintuple(
        message,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE >> "_source",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes["nrel_ui_answer_source"],
    )
    result = []
    for row in search_by_template(templ):
        addr = row.get("_source")
        idtf = get_element_system_identifier(addr)
        if idtf:
            result.append({"idtf": idtf, "scAddr": addr.value})
    return result


def read_history(dialog: ScAddr) -> list[dict[str, Any]]:
    templ = ScTemplate()
    templ.quintuple(
        dialog,
        sc_type.VAR_COMMON_ARC >> "_arc",
        sc_type.VAR_NODE >> "_message",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes["nrel_ui_dialog_message"],
    )
    rows = search_by_template(templ)

    messages: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        message = row.get("_message")
        index = _ordinal(dialog, message)
        item = {
            "scAddr": message.value,
            "role": _role(message),
            "text": _link_value(message, "nrel_ui_value") or "",
            "state": _link_value(message, "nrel_ui_message_state") or kn.STATUS_DONE,
            "createdAt": _link_value(message, "nrel_ui_message_time") or "",
            "model": _link_value(message, "nrel_ui_llm_model"),
            "promptVersion": _link_value(message, "nrel_ui_prompt_version"),
            "knowledgeSource": _link_value(message, "nrel_ui_knowledge_source"),
            "sources": _sources(message),
        }
        messages.append((index, item))

    messages.sort(key=lambda pair: pair[0])
    return [item for _, item in messages]


def _ordinal(dialog: ScAddr, message: ScAddr) -> int:
    templ = ScTemplate()
    templ.quintuple(
        dialog,
        sc_type.VAR_COMMON_ARC,
        message,
        sc_type.VAR_PERM_POS_ARC,
        sc_type.VAR_NODE_ROLE >> "_rrel",
    )
    rows = search_by_template(templ)
    if not rows:
        return 0
    idtf = get_element_system_identifier(rows[0].get("_rrel"))
    try:
        return int(idtf.rsplit("_", 1)[-1])
    except (ValueError, AttributeError):
        return 0


def is_our_class(idtf: str) -> bool:
    return idtf in NEW_CLASSES
