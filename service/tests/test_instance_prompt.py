"""T7: компактный блок экземпляра, бюджеты и режим none без регрессии."""

from __future__ import annotations

import copy

from ostis_ui_assistant.knowledge.instance import ComponentData, InstanceContext
from ostis_ui_assistant.knowledge.render import (
    HISTORY_TOKEN_BUDGET,
    INSTANCE_INSTRUCTION,
    INSTANCE_TOKEN_BUDGET,
    TRUNCATION_MARKER,
    build_messages,
    estimate_tokens,
    render_instance,
)


def _context(*, mode: str = "whole", count: int = 4, selected: int = 1) -> InstanceContext:
    components = [
        ComponentData(
            idtf=f"ex_login_cmp_{index}",
            sc_class="concept_ui_button",
            properties={"text_value": "Войти", "action_id": "auth_submit"},
            inputs=[f"ex_login_cmp_{index - 1}"] if index else [],
            children=[],
        )
        for index in range(count)
    ]
    return InstanceContext(
        mode=mode,
        interface_id="ex_login",
        components=components,
        selected_ids={f"ex_login_cmp_{selected}"},
    )


def test_instance_line_format_is_compact() -> None:
    rendered = render_instance(_context(count=1))
    assert rendered.text.splitlines()[0] == "интерфейс: ex_login | режим: whole | компонентов: 1"
    assert "ex_login_cmp_0 | concept_ui_button | text_value=Войти | action_id=auth_submit" in rendered.text
    assert "связи: ex_login_cmp_0 -nrel_ui_input_target->" not in rendered.text
    assert not rendered.truncated


def test_selection_mode_includes_only_selected_components() -> None:
    rendered = render_instance(_context(mode="selection", count=5, selected=3))
    assert rendered.shown == 1
    assert "ex_login_cmp_3 | concept_ui_button" in rendered.text
    for index in (0, 1, 2, 4):
        assert f"ex_login_cmp_{index} |" not in rendered.text


def test_whole_mode_prioritizes_selected_then_neighbors() -> None:
    rendered = render_instance(_context(mode="whole", count=4, selected=2), budget=200)
    selected_line = next(
        line for line in rendered.text.splitlines() if line.startswith("ex_login_cmp_2 |")
    )
    neighbor_line = next(
        line for line in rendered.text.splitlines() if line.startswith("ex_login_cmp_1 |")
    )
    assert rendered.text.index(selected_line) < rendered.text.index(neighbor_line)
    assert any("связи: ex_login_cmp_2 -nrel_ui_input_target-> ex_login_cmp_1" in line for line in rendered.text.splitlines())


def test_200_components_are_truncated_with_marker() -> None:
    context = _context(count=200, selected=150)
    rendered = render_instance(context)
    marker = TRUNCATION_MARKER.format(shown=rendered.shown, total=200)
    assert rendered.truncated
    assert marker in rendered.text
    assert 0 < rendered.shown < 200
    assert rendered.tokens <= INSTANCE_TOKEN_BUDGET
    assert "ex_login_cmp_150 |" in rendered.text
    assert "ex_login_cmp_199 |" not in rendered.text


def test_none_mode_does_not_change_frozen_prompt(pack: dict, template: str) -> None:
    baseline = build_messages("вопрос о каталоге", pack, template)
    none_context = build_messages("вопрос о каталоге", pack, template, context=InstanceContext())
    assert none_context.messages == baseline.messages
    assert none_context.instance_text == ""


def test_instance_block_is_separate_system_message(pack: dict, template: str) -> None:
    result = build_messages(
        "Что делает ex_login_cmp_10?", pack, template, context=_context(count=3, selected=1)
    )
    instance_message = result.messages[1]
    assert instance_message["role"] == "system"
    assert instance_message["content"].startswith(INSTANCE_INSTRUCTION)
    assert "ex_login_cmp_1 | concept_ui_button" in instance_message["content"]
    assert result.messages[-1]["content"] == "Что делает ex_login_cmp_10?"
    assert result.instance_tokens > 0
    assert result.instance_shown == 3


def test_history_is_trimmed_to_budget(pack: dict, template: str) -> None:
    history = [
        {"role": "user", "content": "старый " * 600},
        {"role": "assistant", "content": "答复" * 1500},
        {"role": "user", "content": "последний вопрос"},
    ]
    result = build_messages("вопрос", pack, template, history=history)
    assert result.history_tokens <= HISTORY_TOKEN_BUDGET
    assert result.messages[-2] == history[-1]
    assert history[0] not in result.messages
    assert history[1] not in result.messages


def test_estimate_tokens_matches_block_measurement() -> None:
    rendered = render_instance(_context())
    assert rendered.tokens == estimate_tokens(rendered.text)


def test_render_does_not_mutate_context() -> None:
    context = _context(count=200)
    before = copy.deepcopy(context)
    render_instance(context)
    assert context == before
