"""Конструкции диалога в sc-памяти."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sc_client.client import search_by_template, set_link_contents
from sc_client.constants import sc_type
from sc_client.models import (
    ScAddr,
    ScLinkContent,
    ScLinkContentType,
    ScTemplate,
)
from sc_kpm import ScKeynodes
from sc_kpm.utils import (
    generate_binary_relation,
    generate_connector,
    generate_link,
    generate_node,
    get_element_system_identifier,
    get_link_content_data,
)
from sc_kpm.utils.action_utils import get_action_result

from ..knowledge.identifiers import NEW_CLASSES
from . import keynodes as kn
from .outcomes import DEFAULT_CODE, MESSAGE_CODES, PENDING_CODE, normalize_code

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
    # Стабильный идентификатор не зависит от ScAddr и переживает пересборку БЗ.
    id_link = generate_link(f"dialog-{uuid.uuid4().hex[:12]}")
    generate_binary_relation(
        sc_type.CONST_COMMON_ARC, dialog, id_link, ScKeynodes["nrel_ui_id"]
    )
    return dialog


def read_dialog_id(dialog: ScAddr) -> str | None:
    return _link_value(dialog, "nrel_ui_id")


def ensure_dialog(dialog: ScAddr | None) -> ScAddr:
    if dialog is not None and dialog.is_valid():
        return dialog
    return create_dialog()


def _message_index(dialog: ScAddr) -> int:
    """Следующий порядковый номер: `max(rrel_N) + 1` из БЗ (B0-2).

    Счётчик в памяти процесса здесь намеренно не используется: два экземпляра
    агента дали бы одинаковые `rrel_N` и перемешали историю. Аренда экземпляра
    (см. `sc/service_state.py`) делает такой запрос безопасным.
    """
    return max(_bulk_ordinals(dialog).values(), default=0) + 1


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
    code: str | None = None,
) -> ScAddr:
    if code is not None and code not in MESSAGE_CODES:
        raise ValueError(f"Неизвестный код исхода сообщения: {code}")
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
    if code:
        code_link = generate_link(code)
        generate_binary_relation(
            sc_type.CONST_COMMON_ARC,
            message,
            code_link,
            ScKeynodes["nrel_ui_message_code"],
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
    code: str = PENDING_CODE,
) -> ScAddr:
    """Pending-сообщение сразу получает служебный код `pending`."""
    return _append_message(
        dialog,
        text,
        "concept_ui_assistant_message",
        state,
        model=model,
        prompt_version=prompt_version,
        sources=sources,
        knowledge_source=knowledge_source,
        code=code,
    )


def append_error_message(
    dialog: ScAddr, reason: str, *, code: str = "internal"
) -> ScAddr:
    return _append_message(
        dialog,
        reason,
        "concept_ui_assistant_message",
        kn.STATUS_ERROR,
        knowledge_source="unknown",
        code=code,
    )


def _set_link_value(message: ScAddr, relation: str, value: str) -> None:
    """Обновляет значение существующего sc-link или создаёт его один раз."""
    link = _find_link(message, relation)
    if link is None:
        link = generate_link(value)
        generate_binary_relation(
            sc_type.CONST_COMMON_ARC, message, link, ScKeynodes[relation]
        )
        return
    set_link_contents(ScLinkContent(value, ScLinkContentType.STRING, link))


def _add_sources(message: ScAddr, sources: list[ScAddr]) -> None:
    if not sources:
        return
    templ = ScTemplate()
    templ.quintuple(
        message,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE >> "_source",
        sc_type.VAR_PERM_POS_ARC,
        ScKeynodes["nrel_ui_answer_source"],
    )
    existing = {row.get("_source").value for row in search_by_template(templ)}
    for source in sources:
        if source.is_valid() and source.value not in existing:
            generate_binary_relation(
                sc_type.CONST_COMMON_ARC,
                message,
                source,
                ScKeynodes["nrel_ui_answer_source"],
            )
            existing.add(source.value)


def complete_assistant_message(
    message: ScAddr,
    text: str,
    *,
    model: str | None = None,
    prompt_version: str | None = None,
    sources: list[ScAddr] | None = None,
    state: str = kn.STATUS_DONE,
    knowledge_source: str | None = None,
    code: str = DEFAULT_CODE,
) -> None:
    """Дописывает pending-сообщение после генерации, не создавая второе сообщение."""
    if code not in MESSAGE_CODES:
        raise ValueError(f"Неизвестный код исхода сообщения: {code}")
    _set_link_value(message, "nrel_ui_value", text)
    _set_link_value(message, "nrel_ui_message_state", state)
    if model:
        _set_link_value(message, "nrel_ui_llm_model", model)
    if prompt_version:
        _set_link_value(message, "nrel_ui_prompt_version", prompt_version)
    if knowledge_source:
        _set_link_value(message, "nrel_ui_knowledge_source", knowledge_source)
    if code:
        _set_link_value(message, "nrel_ui_message_code", code)
    _add_sources(message, sources or [])


def find_link(message: ScAddr, relation: str) -> ScAddr | None:
    return _find_link(message, relation)


def message_time(message: ScAddr) -> str | None:
    return _link_value(message, "nrel_ui_message_time")


def find_assistant_message_in_result(result: ScAddr) -> ScAddr | None:
    """Находит assistant-сообщение внутри структуры результата действия."""
    if not result.is_valid():
        return None
    templ = ScTemplate()
    templ.triple(result, sc_type.VAR_PERM_POS_ARC, sc_type.VAR_NODE >> "_element")
    for row in search_by_template(templ):
        element = row.get("_element")
        if element.is_valid() and _is_class(element, "concept_ui_assistant_message"):
            return element
    return None


def find_assistant_message(action: ScAddr) -> ScAddr | None:
    """Assistant-сообщение, уже связанное с действием через `nrel_result`."""
    return find_assistant_message_in_result(get_action_result(action))


def is_action_initiated(action: ScAddr) -> bool:
    templ = ScTemplate()
    templ.triple(ScKeynodes["action_initiated"], sc_type.VAR_PERM_POS_ARC, action)
    return bool(search_by_template(templ))


def is_action_finished(action: ScAddr) -> bool:
    templ = ScTemplate()
    templ.triple(ScKeynodes["action_finished"], sc_type.VAR_PERM_POS_ARC, action)
    return bool(search_by_template(templ))


def _is_class(element: ScAddr, class_idtf: str) -> bool:
    templ = ScTemplate()
    templ.triple(ScKeynodes[class_idtf], sc_type.VAR_PERM_POS_ARC, element)
    return bool(search_by_template(templ))


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


def _find_link(message: ScAddr, relation: str) -> ScAddr | None:
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
    return rows[0].get("_link")


def _link_value(message: ScAddr, relation: str) -> str | None:
    link = _find_link(message, relation)
    if link is None:
        return None
    return str(get_link_content_data(link))


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
    codes = _bulk_link_values(dialog, "nrel_ui_message_code")
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
                    "code": normalize_code(codes.get(key)),
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
