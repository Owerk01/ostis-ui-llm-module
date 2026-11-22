#!/usr/bin/env python3
"""Смоук-тест действия action_answer_ui_development_question.

Создаёт узел действия в БЗ, ждёт завершения и печатает историю диалога.
Требует запущенного sc-агента (ASSISTANT_TRANSPORT=sc-memory).

Запуск:
    python tools/action_smoke_test.py "Что такое concept_ui_button?"
"""

from __future__ import annotations

import json
import os
import sys
import time

from sc_client import client
from sc_client.client import search_by_template
from sc_client.constants import sc_type
from sc_client.models import ScTemplate
from sc_kpm import ScKeynodes
from sc_kpm.utils import (
    generate_connector,
    generate_link,
    generate_node,
    generate_role_relation,
    get_link_content_data,
)
from sc_kpm.utils.action_utils import get_action_result

SC_WS_URL = os.environ.get("SC_WS_URL", "ws://127.0.0.1:8090/ws_json")
ACTION_CLASS = "action_answer_ui_development_question"
TIMEOUT_S = float(os.environ.get("ACTION_TIMEOUT_S", "30"))


def _init() -> None:
    for idtf in (ACTION_CLASS, "action", "action_initiated", "action_finished"):
        ScKeynodes.resolve(idtf, sc_type.CONST_NODE_CLASS)
    for idtf in ("nrel_ui_dialog_message",):
        ScKeynodes.resolve(idtf, sc_type.CONST_NODE_NON_ROLE)


def _finished(action) -> bool:
    templ = ScTemplate()
    templ.triple(ScKeynodes["action_finished"], sc_type.VAR_PERM_POS_ARC, action)
    return bool(search_by_template(templ))


def _success(action) -> bool:
    templ = ScTemplate()
    templ.triple(
        ScKeynodes["action_finished_successfully"], sc_type.VAR_PERM_POS_ARC, action
    )
    return bool(search_by_template(templ))


def _read_result(action) -> tuple[dict, list]:
    structure = get_action_result(action)
    if not structure.is_valid():
        return {}, []
    templ = ScTemplate()
    templ.triple(structure, sc_type.VAR_PERM_POS_ARC, sc_type.VAR_NODE >> "_element")
    rows = search_by_template(templ)
    links = []
    nodes = []
    for row in rows:
        element = row.get("_element")
        if not element.is_valid():
            continue
        try:
            links.append(str(get_link_content_data(element)))
        except Exception:  # noqa: BLE001 - не link, значит узел
            nodes.append(element)
    return {"result_structure": structure.value, "links": links}, nodes


def _read_history(nodes: list) -> list[dict]:
    from ostis_ui_assistant.sc import dialog_store

    for message in nodes:
        templ = ScTemplate()
        templ.quintuple(
            sc_type.VAR_NODE >> "_dialog",
            sc_type.VAR_COMMON_ARC,
            message,
            sc_type.VAR_PERM_POS_ARC,
            ScKeynodes["nrel_ui_dialog_message"],
        )
        rows = search_by_template(templ)
        if rows:
            return dialog_store.read_history(rows[0].get("_dialog"))
    return []


def main() -> int:
    question = sys.argv[1] if len(sys.argv) > 1 else "Что такое concept_ui_button?"
    client.connect(SC_WS_URL)
    _init()

    action = generate_node(sc_type.CONST_NODE)
    generate_connector(sc_type.CONST_PERM_POS_ARC, ScKeynodes["action"], action)
    generate_connector(sc_type.CONST_PERM_POS_ARC, ScKeynodes[ACTION_CLASS], action)
    question_link = generate_link(question)
    generate_role_relation(action, question_link, ScKeynodes.rrel_index(1))
    generate_connector(sc_type.CONST_PERM_POS_ARC, ScKeynodes["action_initiated"], action)

    started = time.perf_counter()
    while time.perf_counter() - started < TIMEOUT_S:
        if _finished(action):
            break
        time.sleep(0.25)
    else:
        print(json.dumps({"status": "timeout", "action": action.value}, ensure_ascii=False))
        return 2

    status = "successfully" if _success(action) else "unsuccessfully"
    result, result_nodes = _read_result(action)
    payload = {
        "action": action.value,
        "status": status,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "result": result,
        "history": _read_history(result_nodes),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    client.disconnect()
    return 0 if status == "successfully" else 1


if __name__ == "__main__":
    raise SystemExit(main())
