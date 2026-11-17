"""Живые тесты LLM (маркер llm): запускать при поднятой Ollama.

    .venv/bin/pytest -m llm service/tests/test_live_llm.py
"""

from __future__ import annotations

import pytest

from ostis_ui_assistant.config import Settings
from ostis_ui_assistant.knowledge.render import build_messages, load_pack, load_template
from ostis_ui_assistant.knowledge.service import KnowledgeService
from ostis_ui_assistant.llm.base import create_backend

pytestmark = pytest.mark.llm


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings()


def test_live_ollama_answers_with_pack(settings: Settings) -> None:
    backend = create_backend(settings)
    if not backend.health():
        pytest.skip("Ollama недоступна")

    pack = load_pack(settings.knowledge_pack_path)
    template = load_template(settings.prompt_path)
    built = build_messages("Для чего нужен concept_ui_spacer?", pack, template)
    text = "".join(backend.chat(built.messages)).strip()

    assert text
    assert "concept_ui_spacer" in text or "пространств" in text.lower()
    assert backend.last_stats.output_tokens > 0


def test_live_service_gives_sourced_answer(settings: Settings) -> None:
    service = KnowledgeService(settings)
    if not service.backend.health():
        pytest.skip("Ollama недоступна")
    try:
        result = service.answer("Что означает свойство enabled и его значение по умолчанию?")
    finally:
        service.close()

    assert result.text
    assert result.hallucinated is False
    assert any(source["idtf"] == "concept_ui_enabled" for source in result.sources)
    assert result.prompt_tokens > 0


def test_live_service_refuses_unknown_component(settings: Settings) -> None:
    service = KnowledgeService(settings)
    if not service.backend.health():
        pytest.skip("Ollama недоступна")
    try:
        result = service.answer("Есть ли в каталоге компонент «диаграмма Ганта»?")
    finally:
        service.close()

    lowered = result.text.lower()
    assert "нет сведений" in lowered or "отсутств" in lowered
    assert result.hallucinated is False
