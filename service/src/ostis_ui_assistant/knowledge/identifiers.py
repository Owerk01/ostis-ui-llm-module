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
    "nrel_ui_input_target",
    "nrel_ui_output_target",
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
    # B0-2/B0-5: единственный узел состояния сервиса диалога (аренда экземпляра).
    "concept_ui_dialog_service",
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
    # B0-1/B0-2/B1-2: состояние сервиса, heartbeat и машиночитаемый код исхода.
    "nrel_ui_service_heartbeat",
    "nrel_ui_service_state",
    "nrel_ui_message_code",
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

# Идентификаторы среды, которые мы только упоминаем и никогда не объявляем
# в своих .scs. Источник — external/ostis-ui (HTMLTranslatorKeynodes.hpp).
ENVIRONMENT_IDENTIFIERS = {
    "action_translate_sc_to_html",
    "concept_current_ostis_ui_model",
    "nrel_html_representation",
}

# Удалены из keynodes транслятора к 25.11.2026. Держим отдельно, чтобы тест
# test_no_stale_environment_identifiers падал при попытке вернуть имя в знания.
REMOVED_ENVIRONMENT_IDENTIFIERS = {
    "nrel_html_template",
    "nrel_html_parameter_id",
    "nrel_sc_template",
    "rrel_specific_realisation",
}

# Собственные узлы знаний ассистента: принципы, этапы методики и заметки о среде.
# Это не новые системные идентификаторы, а уже объявленные в kb/ui_assistant/*.scs.
KNOWLEDGE_IDENTIFIERS = {
    "ui_principle_accessibility",
    "ui_principle_quick_learning",
    "ui_principle_autonomous_changeability",
    "ui_principle_reuse",
    "ui_principle_semantic_compatibility",
    "ui_methodology_processes",
    "ui_stage_initial_task",
    "ui_stage_initial_generation",
    "ui_stage_initial_testing",
    "ui_stage_editing_request",
    "ui_stage_editing_apply",
    "ui_stage_editing_testing",
    "ui_stage_adaptation_collect",
    "ui_stage_adaptation_decision",
    "ui_stage_adaptation_rebuild",
    "ui_stage_adaptation_update_model",
    "ui_env_tool_modules",
    "ui_env_solver_modules",
    "ui_env_kb_module",
    "ui_env_target_system",
    "ui_env_html_representation",
}

ALL_IDENTIFIERS = (
    EXISTING_CLASSES
    | EXISTING_RELATIONS
    | NEW_CLASSES
    | NEW_RELATIONS
    | NEW_ACTIONS
    | STANDARD_USED
    | ENVIRONMENT_IDENTIFIERS
    | KNOWLEDGE_IDENTIFIERS
)
