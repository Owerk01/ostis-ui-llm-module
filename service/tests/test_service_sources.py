"""Основания ответов о принципах, методике и среде."""

from __future__ import annotations

from typing import Iterator

from ostis_ui_assistant.config import Settings
from ostis_ui_assistant.knowledge.service import KnowledgeService
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


def _answer(question: str, answer: str, settings: Settings) -> list[dict[str, str]]:
    service = KnowledgeService(
        settings.model_copy(update={"knowledge_source": "fallback"}),
        backend=FixtureBackend(answer),
    )
    try:
        return service.answer(question).sources
    finally:
        service.close()


def test_sources_for_principle_question(settings: Settings) -> None:
    sources = _answer(
        "В чём суть принципа доступности?",
        "`ui_principle_accessibility` — простые средства разработки.",
        settings,
    )
    assert any(source["idtf"] == "ui_principle_accessibility" for source in sources)


def test_sources_for_methodology_and_environment(settings: Settings) -> None:
    sources = _answer(
        "Как устроена среда?",
        "Методика описана в `ui_methodology_processes`, среда — в `ui_env_kb_module`.",
        settings,
    )
    idtfs = {source["idtf"] for source in sources}
    assert "ui_methodology_processes" in idtfs
    assert "ui_env_kb_module" in idtfs
