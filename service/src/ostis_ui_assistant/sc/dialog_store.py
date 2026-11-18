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


# Счётчик порядковых номеров живёт в памяти процесса: полный поиск по БЗ
# делается только при первом обращении к диалогу.
_message_counters: dict[int, int] = {}


def reset_counters() -> None:
    """Сброс счётчиков (используется тестами и при смене БЗ)."""
    _message_counters.clear()


def _message_index(dialog: ScAddr) -> int:
    key = dialog.value
    if key not in _message_counters:
        templ = ScTemplate()
        templ.quintuple(
            dialog,
            sc_type.VAR_COMMON_ARC,
            sc_type.VAR_NODE >> "_message",
            sc_type.VAR_PERM_POS_ARC,
            ScKeynodes["nrel_ui_dialog_message"],
        )
        _message_counters[key] = len(search_by_template(templ))
    _message_counters[key] += 1
    return _message_counters[key]


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


def _bulk_link_values(dialog: ScAddr, relation: str) -> dict[int, str]:
    """Все значения одного отношения для всех сообщений диалога одним запросом."""
    templ = ScTemplate()
    templ.quintuple(
        dialog,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE >> "_message",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes["nrel_ui_dialog_message"],
    )
    templ.quintuple(
        "_message",
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE_LINK >> "_link",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes[relation],
    )
    result: dict[int, str] = {}
    for row in search_by_template(templ):
        result[row.get("_message").value] = str(get_link_content_data(row.get("_link")))
    return result


def _bulk_roles() -> dict[int, str]:
    result: dict[int, str] = {}
    for class_idtf, role in (
        ("concept_ui_user_message", "user"),
        ("concept_ui_assistant_message", "assistant"),
    ):
        templ = ScTemplate()
        templ.triple(ScKeynodes[class_idtf], sc_type.VAR_PERM_POS_ARC, sc_type.VAR_NODE >> "_message")
        for row in search_by_template(templ):
            result[row.get("_message").value] = role
    return result


def _bulk_ordinals(dialog: ScAddr) -> dict[int, int]:
    templ = ScTemplate()
    templ.quintuple(
        dialog,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE >> "_message",
        sc_type.VAR_PERM_POS_ARC,
        sc_type.VAR_NODE_ROLE >> "_rrel",
    )
    result: dict[int, int] = {}
    for row in search_by_template(templ):
        idtf = get_element_system_identifier(row.get("_rrel")) or ""
        try:
            result[row.get("_message").value] = int(idtf.rsplit("_", 1)[-1])
        except ValueError:
            result[row.get("_message").value] = 0
    return result


def _bulk_sources(dialog: ScAddr) -> dict[int, list[dict[str, str]]]:
    templ = ScTemplate()
    templ.quintuple(
        dialog,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE >> "_message",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes["nrel_ui_dialog_message"],
    )
    templ.quintuple(
        "_message",
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE >> "_source",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes["nrel_ui_answer_source"],
    )
    result: dict[int, list[dict[str, str]]] = {}
    for row in search_by_template(templ):
        addr = row.get("_source")
        idtf = get_element_system_identifier(addr)
        if idtf:
            result.setdefault(row.get("_message").value, []).append(
                {"idtf": idtf, "scAddr": addr.value}
            )
    return result


def read_history(dialog: ScAddr) -> list[dict[str, Any]]:
    """Читает историю пакетно: число запросов не зависит от числа сообщений."""
    templ = ScTemplate()
    templ.quintuple(
        dialog,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE >> "_message",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes["nrel_ui_dialog_message"],
    )
    rows = search_by_template(templ)
    messages = [row.get("_message") for row in rows]

    texts = _bulk_link_values(dialog, "nrel_ui_value")
    states = _bulk_link_values(dialog, "nrel_ui_message_state")
    times = _bulk_link_values(dialog, "nrel_ui_message_time")
    models = _bulk_link_values(dialog, "nrel_ui_llm_model")
    versions = _bulk_link_values(dialog, "nrel_ui_prompt_version")
    sources_map = _bulk_link_values(dialog, "nrel_ui_knowledge_source")
    roles = _bulk_roles()
    ordinals = _bulk_ordinals(dialog)
    sources = _bulk_sources(dialog)

    items: list[tuple[int, dict[str, Any]]] = []
    for message in messages:
        key = message.value
        items.append(
            (
                ordinals.get(key, 0),
                {
                    "scAddr": key,
                    "role": roles.get(key, "assistant"),
                    "text": texts.get(key, ""),
                    "state": states.get(key) or kn.STATUS_DONE,
                    "createdAt": times.get(key, ""),
                    "model": models.get(key),
                    "promptVersion": versions.get(key),
                    "knowledgeSource": sources_map.get(key),
                    "sources": sources.get(key, []),
                },
            )
        )
    items.sort(key=lambda pair: pair[0])
    return [item for _, item in items]


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
