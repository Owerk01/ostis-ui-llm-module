#!/usr/bin/env python3
"""Смоук-тест БЗ (M0-T6).

Проверяет, что:
1. sc-machine доступна по SC_WS_URL;
2. резолвятся ключевые узлы схемы UI;
3. пример ex_login загружен;
4. у ex_login читаются компоненты через nrel_ui_has_component,
   у компонентов определяется тип из concept_ui_object.

Скрипт ничего не пишет в БЗ.
"""

from __future__ import annotations

import os
import sys

from sc_client import client
from sc_client.client import search_by_template
from sc_client.constants import sc_type
from sc_client.models import ScTemplate
from sc_kpm import ScKeynodes
from sc_kpm.utils import get_element_system_identifier

SC_WS_URL = os.environ.get("SC_WS_URL", "ws://127.0.0.1:8090/ws_json")

# Классы типов компонентов из docs/abstract_ui_model.scs (16 типов).
COMPONENT_CLASSES = {
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
}


def fail(message: str) -> None:
    print(f"ОШИБКА: {message}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    print(f"Подключение к {SC_WS_URL} ...")
    client.connect(SC_WS_URL)

    interface_cls = ScKeynodes.resolve("concept_ui_interface", sc_type.CONST_NODE_CLASS)
    has_component = ScKeynodes.resolve("nrel_ui_has_component", sc_type.CONST_NODE_NON_ROLE)
    object_cls = ScKeynodes.resolve("concept_ui_object", sc_type.CONST_NODE_CLASS)
    inclusion = ScKeynodes.resolve("nrel_inclusion", sc_type.CONST_NODE_NON_ROLE)

    if not interface_cls.is_valid():
        fail("не резолвится concept_ui_interface — схема UI не загружена")
    if not has_component.is_valid():
        fail("не резолвится nrel_ui_has_component — схема UI не загружена")
    print(f"concept_ui_interface = {interface_cls}")
    print(f"nrel_ui_has_component = {has_component}")

    if not object_cls.is_valid() or not inclusion.is_valid():
        fail("не резолвятся concept_ui_object / nrel_inclusion")

    ex_login = ScKeynodes.resolve("ex_login", sc_type.CONST_NODE)
    if not ex_login.is_valid():
        fail("не найден ex_login — загрузите ui_examples/Вход_в_систему__ex_login.scs")

    template = ScTemplate()
    template.quintuple(
        ex_login,
        sc_type.VAR_COMMON_ARC,
        sc_type.VAR_NODE >> "_cmp",
        sc_type.VAR_PERM_POS_ARC,
        has_component,
    )
    rows = search_by_template(template)
    if not rows:
        fail("у ex_login нет компонентов через nrel_ui_has_component")

    print(f"components: {len(rows)}")
    type_count = 0
    for row in rows:
        component = row.get("_cmp")
        component_idtf = get_element_system_identifier(component)

        # SCs `component <- concept_ui_button;;` — дуга идёт ОТ класса К компоненту.
        type_template = ScTemplate()
        type_template.triple(
            sc_type.VAR_NODE_CLASS >> "_type",
            sc_type.VAR_PERM_POS_ARC,
            component,
        )
        component_type = "?"
        for type_row in search_by_template(type_template):
            type_idtf = get_element_system_identifier(type_row.get("_type"))
            if type_idtf in COMPONENT_CLASSES:
                component_type = type_idtf
                type_count += 1
                break

        print(f"  {component_idtf}: {component_type}")

    if type_count == 0:
        fail("ни у одного компонента не определён тип из concept_ui_*")

    print("СМОУК ПРОЙДЕН")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        if client.is_connected():
            client.disconnect()
