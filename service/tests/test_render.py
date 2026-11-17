"""Тесты рендера промпта и бюджета токенов (M1-T3)."""

from __future__ import annotations

import copy

from ostis_ui_assistant.knowledge.render import (
    FEW_SHOT,
    TOKEN_BUDGET,
    build_messages,
    build_prompt,
    estimate_tokens,
    render_component_types,
    render_properties,
)


def test_knowledge_fits_budget(pack: dict, template: str) -> None:
    result = build_prompt(pack, template)
    assert result.knowledge_tokens <= TOKEN_BUDGET
    assert result.truncated_sections == []


def test_component_render_one_line_per_type(pack: dict) -> None:
    text = render_component_types(pack)
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == len(pack["component_types"])
    assert "concept_ui_button | Кнопка" in text
    assert "по умолчанию:" in text


def test_properties_render_one_line_per_property(pack: dict) -> None:
    text = render_properties(pack)
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == len(pack["properties"])
    assert "concept_ui_action_id | action_id" in text
    assert "concept_ui_font_size | font_size" in text


def test_prompt_contains_all_sections_and_question(pack: dict, template: str) -> None:
    result = build_messages("Что такое concept_ui_button?", pack, template)
    assert result.messages[0]["role"] == "system"
    assert result.messages[-1] == {
        "role": "user",
        "content": "Что такое concept_ui_button?",
    }
    system = result.messages[0]["content"]
    assert "concept_ui_button" in system
    assert "<catalog_types>" in system
    assert "{{component_types}}" not in system


def test_few_shot_pairs_preserved(pack: dict, template: str) -> None:
    result = build_messages("вопрос", pack, template)
    body = result.messages[1:-1]
    assert body == FEW_SHOT
    assert len(body) % 2 == 0
    for pair in zip(body[::2], body[1::2]):
        assert pair[0]["role"] == "user"
        assert pair[1]["role"] == "assistant"


def test_budget_truncation_falls_back_to_titles(pack: dict, template: str) -> None:
    inflated = copy.deepcopy(pack)
    inflated["principles"] = [
        {"idtf": f"ui_principle_{index}", "title_ru": "Принцип", "text_ru": "текст " * 400}
        for index in range(10)
    ]
    result = build_prompt(inflated, template, budget=1000)
    assert result.truncated_sections == ["methodology_stages", "environment_notes"]
    assert result.knowledge_tokens <= estimate_tokens(result.knowledge_text)


def test_estimate_tokens_is_ceil_third() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("abcd") == 2
