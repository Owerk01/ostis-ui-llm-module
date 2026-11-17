"""Рендер knowledge pack в компактный системный промпт (M1-T3).

Бюджет: оценка len(text)/3 для русского, не более 3500 токенов на блок ЗНАНИЯ.
При превышении усекаем methodology_stages и environment_notes до заголовков.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TOKEN_BUDGET = 3500
PROPERTY_ORDER = [
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
]

FEW_SHOT: list[dict[str, str]] = [
    {
        "role": "user",
        "content": "Чем button отличается от menu_item?",
    },
    {
        "role": "assistant",
        "content": (
            "`concept_ui_button` — самостоятельная кнопка, инициирующая действие; "
            "текст задаётся свойством `text_value`, а действие — `action_id`. "
            "`concept_ui_menu_item` — пункт меню, он имеет смысл внутри "
            "`concept_ui_menu` или `concept_ui_menu_bar`, куда включается отношением "
            "`nrel_ui_contains`. Оба типа входят в `concept_ui_object` и имеют "
            "одинаковый набор свойств."
        ),
    },
    {
        "role": "user",
        "content": "Добавь мне выпадающий список с тремя вариантами.",
    },
    {
        "role": "assistant",
        "content": (
            "Я не изменяю интерфейс — это делается в визуальном редакторе. Для выбора "
            "одного значения из набора в каталоге предусмотрен тип `concept_ui_select`, "
            "для отображения набора элементов — `concept_ui_list`. Уточни, нужен ли "
            "выбор значения или показ списка, и я расскажу о свойствах соответствующего "
            "компонента."
        ),
    },
]


@dataclass
class PromptBuildResult:
    messages: list[dict[str, str]]
    system_prompt: str
    knowledge_text: str
    knowledge_tokens: int
    system_tokens: int
    truncated_sections: list[str] = field(default_factory=list)


def estimate_tokens(text: str) -> int:
    """Оценка для русского текста: len/3, округление вверх."""
    return math.ceil(len(text) / 3)


def load_pack(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _format_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, str) and value == "":
        return '""'
    return str(value)


def _global_defaults(pack: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for prop in pack.get("properties", []):
        if prop.get("default") is not None:
            result[prop["key"]] = prop["default"]
    return result


def _type_defaults_line(defaults: dict[str, Any], global_defaults: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in PROPERTY_ORDER:
        if key not in defaults or key == "name":
            continue
        value = defaults[key]
        if key in {"width", "height"} or value != global_defaults.get(key):
            if value is None or value == "":
                continue
            parts.append(f"{key}={_format_value(value)}")
    return ", ".join(parts)


def render_component_types(pack: dict[str, Any]) -> str:
    global_defaults = _global_defaults(pack)
    lines: list[str] = []
    for item in pack.get("component_types", []):
        defaults = _type_defaults_line(item.get("defaults", {}), global_defaults)
        line = (
            f"{item['sc_class']} | {item['label_ru']} | ключ: {item['type_id']} "
            f"| назначение: {item.get('purpose_ru', '')}"
        )
        if defaults:
            line += f" | по умолчанию: {defaults}"
        lines.append(line)
    return "\n".join(lines)


def render_properties(pack: dict[str, Any]) -> str:
    lines: list[str] = []
    for prop in pack.get("properties", []):
        default = prop.get("default")
        if default is None:
            default_text = prop.get("default_note_ru", "зависит от типа")
        else:
            default_text = _format_value(default)
        line = (
            f"{prop['sc_class']} | {prop['key']} | {prop.get('type', 'string')} "
            f"| по умолчанию: {default_text} | смысл: {prop.get('meaning_ru', '')}"
        )
        allowed = prop.get("allowed_values")
        if allowed:
            allowed_text = allowed if isinstance(allowed, str) else " / ".join(map(str, allowed))
            line += f" | допустимо: {allowed_text}"
        lines.append(line)
    return "\n".join(lines)


def render_relations(pack: dict[str, Any]) -> str:
    return "\n".join(
        f"{item['idtf']} | {item.get('meaning_ru', '')}"
        for item in pack.get("relations", [])
    )


def _render_knowledge_items(items: list[dict[str, Any]], titles_only: bool = False) -> str:
    lines: list[str] = []
    for item in items:
        title = item.get("title_ru") or item.get("idtf", "")
        text = item.get("text_ru", "")
        if titles_only or not text:
            lines.append(f"{item.get('idtf', '')} | {title}")
        else:
            lines.append(f"{item.get('idtf', '')} | {title} | {text}")
    return "\n".join(lines)


def render_sections(pack: dict[str, Any], truncate: bool = False) -> dict[str, str]:
    return {
        "component_types": render_component_types(pack),
        "properties": render_properties(pack),
        "relations": render_relations(pack),
        "principles": _render_knowledge_items(pack.get("principles", []), titles_only=truncate),
        "methodology_stages": _render_knowledge_items(
            pack.get("methodology_stages", []), titles_only=truncate
        ),
        "environment_notes": _render_knowledge_items(
            pack.get("environment_notes", []), titles_only=truncate
        ),
    }


def _fill_template(template: str, sections: dict[str, str]) -> str:
    result = template
    for key, value in sections.items():
        result = result.replace("{{" + key + "}}", value or "— нет сведений —")
    return result


def build_prompt(
    pack: dict[str, Any],
    template: str,
    *,
    budget: int = TOKEN_BUDGET,
) -> PromptBuildResult:
    sections = render_sections(pack, truncate=False)
    knowledge_text = "\n".join(sections.values())
    knowledge_tokens = estimate_tokens(knowledge_text)
    truncated: list[str] = []

    if knowledge_tokens > budget:
        sections = render_sections(pack, truncate=True)
        knowledge_text = "\n".join(sections.values())
        knowledge_tokens = estimate_tokens(knowledge_text)
        truncated = ["methodology_stages", "environment_notes"]
        logger.warning(
            "Бюджет промпта превышен: %s токенов > %s; methodology/environment усечены",
            knowledge_tokens,
            budget,
        )

    system_prompt = _fill_template(template, sections)
    return PromptBuildResult(
        messages=[],
        system_prompt=system_prompt,
        knowledge_text=knowledge_text,
        knowledge_tokens=knowledge_tokens,
        system_tokens=estimate_tokens(system_prompt),
        truncated_sections=truncated,
    )


def build_messages(
    question: str,
    pack: dict[str, Any],
    template: str,
    *,
    budget: int = TOKEN_BUDGET,
    include_few_shot: bool = True,
) -> PromptBuildResult:
    result = build_prompt(pack, template, budget=budget)
    messages: list[dict[str, str]] = [{"role": "system", "content": result.system_prompt}]
    if include_few_shot:
        messages.extend(FEW_SHOT)
    messages.append({"role": "user", "content": question})
    result.messages = messages
    return result
