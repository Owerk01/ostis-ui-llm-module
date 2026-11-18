"""Разрешение ключевых узлов ассистента."""

from __future__ import annotations

from sc_client.constants import sc_type
from sc_kpm import ScKeynodes

KEYNODES: dict[str, int] = {
    "concept_ui_dialog": sc_type.CONST_NODE_CLASS,
    "concept_ui_dialog_message": sc_type.CONST_NODE_CLASS,
    "concept_ui_user_message": sc_type.CONST_NODE_CLASS,
    "concept_ui_assistant_message": sc_type.CONST_NODE_CLASS,
    "concept_ui_knowledge": sc_type.CONST_NODE_CLASS,
    "concept_ui_development_principle": sc_type.CONST_NODE_CLASS,
    "concept_ui_development_stage": sc_type.CONST_NODE_CLASS,
    "concept_ui_environment_note": sc_type.CONST_NODE_CLASS,
    "action_answer_ui_development_question": sc_type.CONST_NODE_CLASS,
    "nrel_ui_dialog_message": sc_type.CONST_NODE_NON_ROLE,
    "nrel_ui_message_time": sc_type.CONST_NODE_NON_ROLE,
    "nrel_ui_message_state": sc_type.CONST_NODE_NON_ROLE,
    "nrel_ui_answer_source": sc_type.CONST_NODE_NON_ROLE,
    "nrel_ui_llm_model": sc_type.CONST_NODE_NON_ROLE,
    "nrel_ui_prompt_version": sc_type.CONST_NODE_NON_ROLE,
    "nrel_ui_knowledge_text": sc_type.CONST_NODE_NON_ROLE,
    "nrel_ui_knowledge_source": sc_type.CONST_NODE_NON_ROLE,
    "nrel_ui_dialog_context": sc_type.CONST_NODE_NON_ROLE,
    "nrel_ui_value": sc_type.CONST_NODE_NON_ROLE,
    "nrel_main_idtf": sc_type.CONST_NODE_NON_ROLE,
}

STATUS_DONE = "done"
STATUS_ERROR = "error"
STATUS_CANCELLED = "cancelled"


def init_keynodes() -> None:
    for idtf, node_type in KEYNODES.items():
        ScKeynodes.resolve(idtf, node_type)
