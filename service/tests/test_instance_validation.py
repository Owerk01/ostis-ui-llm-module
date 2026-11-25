"""T8: валидация id экземпляра и основания для ответов о нём."""

from __future__ import annotations

from typing import Iterator

from sc_client.models import ScAddr

from ostis_ui_assistant.config import Settings
from ostis_ui_assistant.knowledge.instance import ComponentData, InstanceContext
from ostis_ui_assistant.knowledge.service import KnowledgeService
from ostis_ui_assistant.knowledge.validate import REMOVAL_NOTE
from ostis_ui_assistant.llm.base import LLMStats


class FixtureBackend:
    model = "dummy"

    def __init__(self, answer: str) -> None:
        self.answer = answer

    def chat(
        self, messages: list[dict[str, str]], *, max_tokens: int | None = None
    ) -> Iterator[str]:
        yield self.answer

    @property
    def last_stats(self) -> LLMStats:
        return LLMStats()

    def health(self) -> bool:
        return True


def _answer(
    settings: Settings, question: str, answer: str, context: InstanceContext | None = None
):
    service = KnowledgeService(
        settings.model_copy(update={"knowledge_source": "fallback"}),
        backend=FixtureBackend(answer),
    )
    try:
        return service.answer(question, context=context)
    finally:
        service.close()


def _context() -> InstanceContext:
    return InstanceContext(
        mode="whole",
        interface_id="ex_login",
        interface_addr=ScAddr(2001),
        components=[
            ComponentData(idtf="ex_login_cmp_10", addr=ScAddr(2002)),
            ComponentData(idtf="ex_login_cmp_5", addr=ScAddr(2003)),
        ],
    )


def test_loaded_instance_id_is_kept_and_becomes_source(settings: Settings) -> None:
    answer = "Компонент ex_login_cmp_10 — кнопка входа."
    result = _answer(settings, "что делает кнопка?", answer, _context())

    assert result.text == answer
    assert result.validation_removed == []
    assert result.unknown_in_final_instance == []
    assert any(source["idtf"] == "ex_login_cmp_10" for source in result.sources)


def test_invented_instance_id_is_removed_with_note(settings: Settings) -> None:
    result = _answer(
        settings,
        "что делает кнопка?",
        "Компонент ex_login_cmp_999 не существует.",
        _context(),
    )

    assert "ex_login_cmp_999" not in result.text
    assert REMOVAL_NOTE in result.text
    assert any("ex_login_cmp_999" in item for item in result.validation_removed)
    assert not any(source["idtf"] == "ex_login_cmp_999" for source in result.sources)


def test_mode_none_cuts_component_ids(settings: Settings) -> None:
    result = _answer(
        settings,
        "что делает ex_login_cmp_10?",
        "Компонент ex_login_cmp_10 не описан в каталоге.",
        InstanceContext(),
    )

    assert "ex_login_cmp_10" not in result.text
    assert REMOVAL_NOTE in result.text
    assert result.unknown_in_final_instance == []


def test_unread_interface_id_is_not_allowed(settings: Settings) -> None:
    context = InstanceContext(mode="whole", interface_id="ex_unknown")
    result = _answer(
        settings, "что это?", "Интерфейс ex_unknown описан в каталоге.", context
    )

    assert "ex_unknown" not in result.text
    assert REMOVAL_NOTE in result.text
    assert not any(source["idtf"] == "ex_unknown" for source in result.sources)


def test_interface_id_from_question_is_not_hallucination(settings: Settings) -> None:
    answer = "В базе знаний нет сведений об ex_login."
    result = _answer(settings, "Что известно об ex_login?", answer)

    assert result.text == answer
    assert result.validation_removed == []
    assert result.unknown_in_final_instance == []
    assert not any(source["idtf"] == "ex_login" for source in result.sources)
