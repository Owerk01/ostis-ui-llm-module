"""Замороженный контракт идентификаторов.

Существующие идентификаторы только упоминаются; новые принадлежат ассистенту.
"""

from __future__ import annotations

EXISTING_CLASSES = {
    "concept_ui_interface",
    "concept_ui_object",
    "concept_ui_image",
    "concept_ui_sound",
    "concept_ui_text",
    "concept_ui_divider",
    "concept_ui_spacer",
    "concept_ui_menu",
    "concept_ui_menu_bar",
    "concept_ui_list",
    "concept_ui_scroll",
    "concept_ui_window",
    "concept_ui_text_field",
    "concept_ui_text_area",
    "concept_ui_slider",
    "concept_ui_select",
    "concept_ui_button",
    "concept_ui_menu_item",
    "concept_ui_name",
    "concept_ui_x",
    "concept_ui_y",
    "concept_ui_width",
    "concept_ui_height",
    "concept_ui_order",
    "concept_ui_visible",
    "concept_ui_enabled",
    "concept_ui_opacity",
    "concept_ui_text_value",
    "concept_ui_tooltip",
    "concept_ui_action_id",
    "concept_ui_background_color",
    "concept_ui_color",
    "concept_ui_border_color",
    "concept_ui_border_width",
    "concept_ui_border_style",
    "concept_ui_corner_radius",
    "concept_ui_font_size",
    "concept_ui_font_weight",
    "concept_ui_text_align",
    "concept_ui_padding",
    "concept_ui_margin",
    "concept_ui_min_width",
    "concept_ui_min_height",
    "concept_ui_max_width",
    "concept_ui_max_height",
}

EXISTING_RELATIONS = {
    "nrel_inclusion",
    "nrel_ui_contains",
    "nrel_ui_has_component",
    "nrel_ui_id",
    "nrel_ui_value",
    "nrel_main_idtf",
    "nrel_system_identifier",
}

NEW_CLASSES = {
    "concept_ui_dialog",
    "concept_ui_dialog_message",
    "concept_ui_user_message",
    "concept_ui_assistant_message",
    "concept_ui_knowledge",
    "concept_ui_development_principle",
    "concept_ui_development_stage",
    "concept_ui_environment_note",
}

NEW_RELATIONS = {
    "nrel_ui_dialog_message",
    "nrel_ui_message_time",
    "nrel_ui_message_state",
    "nrel_ui_answer_source",
    "nrel_ui_llm_model",
    "nrel_ui_prompt_version",
    "nrel_ui_knowledge_text",
    "nrel_ui_knowledge_source",
    "nrel_ui_dialog_context",
}

NEW_ACTIONS = {
    "action_answer_ui_development_question",
}

STANDARD_USED = {
    "action",
    "action_initiated",
    "action_finished",
    "action_finished_successfully",
    "action_finished_unsuccessfully",
    "lang_ru",
    "rrel_1",
    "rrel_2",
    "rrel_3",
    "rrel_4",
    "rrel_5",
}

PROPERTY_KEYS = {
    "name",
    "x",
    "y",
    "width",
    "height",
    "order",
    "visible",
    "enabled",
    "opacity",
    "text_value",
    "tooltip",
    "action_id",
    "background_color",
    "color",
    "border_color",
    "border_width",
    "border_style",
    "corner_radius",
    "font_size",
    "font_weight",
    "text_align",
    "padding",
    "margin",
    "min_width",
    "min_height",
    "max_width",
    "max_height",
}

ALL_IDENTIFIERS = (
    EXISTING_CLASSES
    | EXISTING_RELATIONS
    | NEW_CLASSES
    | NEW_RELATIONS
    | NEW_ACTIONS
    | STANDARD_USED
)
