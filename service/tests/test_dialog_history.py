"""T9: история диалога в промпте, анафора и независимость бюджета знаний."""

from __future__ import annotations

from typing import Iterator

from ostis_ui_assistant.config import Settings
from ostis_ui_assistant.knowledge.history import prepare_history
from ostis_ui_assistant.knowledge.render import (
    FEW_SHOT,
    HISTORY_INSTRUCTION,
    HISTORY_TOKEN_BUDGET,
    HISTORY_TRUNCATION_MARKER,
    build_messages,
    fit_history,
)
from ostis_ui_assistant.knowledge.service import KnowledgeService
from ostis_ui_assistant.llm.base import LLMStats


class CapturingBackend:
    model = "dummy"

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    def chat(
        self, messages: list[dict[str, str]], *, max_tokens: int | None = None
    ) -> Iterator[str]:
        self.messages = [dict(message) for message in messages]
        has_referent = any(
            message["content"] == "что такое concept_ui_text_field?"
            for message in messages
        )
        answer = (
            "Свойства concept_ui_text_field: text_value."
            if has_referent
            else "Не могу определить, о чём речь."
        )
        yield answer

    @property
    def last_stats(self) -> LLMStats:
        return LLMStats()

    def health(self) -> bool:
        return True


def _message(index: int, *, role: str = "user") -> dict[str, str]:
    return {
        "id": f"m{index}",
        "role": role,
        "text": f"сообщение {index}",
        "state": "done",
        "code": "ok",
    }


def test_prepare_history_limits_and_excludes_current_and_pending() -> None:
    messages = [
        _message(index, role="user" if index % 2 else "assistant")
        for index in range(8)
    ]
    messages.append(
        {
            "id": "pending",
            "role": "assistant",
            "text": "ещё генерируется",
            "state": "done",
            "code": "pending",
        }
    )
    messages.append({**_message(99), "state": "error", "code": "internal"})
    current = {**_message(100), "text": "текущий вопрос"}

    result = prepare_history(
        [*messages, current], 6, exclude_ids={current["id"]}
    )

    assert [item["content"] for item in result] == [
        f"сообщение {index}" for index in range(2, 8)
    ]
    assert all(item["content"] != current["text"] for item in result)
    assert prepare_history(messages, 0) == []


def test_two_turns_resolve_anaphora(settings: Settings) -> None:
    backend = CapturingBackend()
    service = KnowledgeService(
        settings.model_copy(update={"knowledge_source": "fallback"}), backend=backend
    )
    try:
        result = service.answer(
            "какие у него свойства?",
            history=[
                {**_message(1), "text": "что такое concept_ui_text_field?"},
                {
                    **_message(2, role="assistant"),
                    "text": "concept_ui_text_field — поле ввода текста.",
                },
            ],
        )
    finally:
        service.close()

    assert "concept_ui_text_field" in result.text
    assert result.history_messages == 2
    assert result.history_tokens > 0
    contents = [message["content"] for message in backend.messages]
    assert "что такое concept_ui_text_field?" in contents
    assert "concept_ui_text_field — поле ввода текста." in contents
    assert contents[-1] == "какие у него свойства?"
    assert contents.index("что такое concept_ui_text_field?") < len(contents) - 1


def test_disabled_history_does_not_reach_prompt(settings: Settings) -> None:
    backend = CapturingBackend()
    service = KnowledgeService(
        settings.model_copy(
            update={"knowledge_source": "fallback", "dialog_history_turns": 0}
        ),
        backend=backend,
    )
    try:
        service.answer(
            "какие у него свойства?",
            history=[{**_message(1), "text": "что такое concept_ui_text_field?"}],
        )
    finally:
        service.close()

    assert "что такое concept_ui_text_field?" not in [
        message["content"] for message in backend.messages
    ]


def test_history_after_few_shot_does_not_shrink_knowledge(
    pack: dict, template: str
) -> None:
    history = [
        {"role": "user", "content": f"сообщение {index} " * 100}
        for index in range(20)
    ]
    without = build_messages("вопрос", pack, template)
    with_history = build_messages("вопрос", pack, template, history=history)

    assert with_history.knowledge_tokens == without.knowledge_tokens
    assert with_history.system_prompt == without.system_prompt
    assert with_history.messages[0] == without.messages[0]
    assert with_history.messages[1 : 1 + len(FEW_SHOT)] == FEW_SHOT
    kept, _ = fit_history(history)
    assert with_history.messages[1 + len(FEW_SHOT)] == {
        "role": "system",
        "content": HISTORY_INSTRUCTION + "\n" + HISTORY_TRUNCATION_MARKER,
    }
    assert with_history.messages[2 + len(FEW_SHOT) : -1] == kept
    assert len(kept) < len(history)
    assert with_history.messages[-1] == {"role": "user", "content": "вопрос"}
    assert 0 < with_history.history_tokens <= HISTORY_TOKEN_BUDGET
    assert with_history.history_truncated is True


def test_history_instruction_is_added_only_with_history(
    pack: dict, template: str
) -> None:
    without = build_messages("вопрос", pack, template)
    with_history = build_messages(
        "вопрос", pack, template, history=[{"role": "user", "content": "привет"}]
    )
    assert HISTORY_INSTRUCTION not in [item["content"] for item in without.messages]
    assert {"role": "system", "content": HISTORY_INSTRUCTION} in with_history.messages
    assert with_history.history_truncated is False
