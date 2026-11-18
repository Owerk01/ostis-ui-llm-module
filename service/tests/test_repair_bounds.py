"""Repair-запрос ограничен дедлайном и отменой."""

from __future__ import annotations

import threading
import time
from typing import Iterator

from ostis_ui_assistant.config import Settings
from ostis_ui_assistant.knowledge.service import KnowledgeService
from ostis_ui_assistant.llm.base import LLMStats


class CountingBackend:
    model = "dummy"

    def __init__(self) -> None:
        self.calls = 0

    def chat(
        self, messages: list[dict[str, str]], *, max_tokens: int | None = None
    ) -> Iterator[str]:
        self.calls += 1
        yield "исправленный ответ"

    @property
    def last_stats(self) -> LLMStats:
        return LLMStats()

    def health(self) -> bool:
        return True


def make_service(settings: Settings, backend: CountingBackend) -> KnowledgeService:
    return KnowledgeService(
        settings.model_copy(update={"knowledge_source": "fallback"}), backend=backend
    )


def test_repair_skipped_after_deadline(settings: Settings) -> None:
    backend = CountingBackend()
    service = make_service(settings, backend)
    try:
        result = service._repair(
            "answers `concept_ui_fake`", ["concept_ui_fake"], deadline=time.perf_counter() - 1
        )
        assert result == "answers `concept_ui_fake`"
        assert backend.calls == 0
    finally:
        service.close()


def test_repair_skipped_when_cancelled(settings: Settings) -> None:
    backend = CountingBackend()
    service = make_service(settings, backend)
    event = threading.Event()
    event.set()
    try:
        result = service._repair(
            "answers `concept_ui_fake`", ["concept_ui_fake"], cancel_event=event
        )
        assert result == "answers `concept_ui_fake`"
        assert backend.calls == 0
    finally:
        service.close()
