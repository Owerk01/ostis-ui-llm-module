"""Калибровка оценки токенов по фактическому размеру промпта."""

from __future__ import annotations

from ostis_ui_assistant.knowledge.tokens import near_context_limit


def test_near_context_limit() -> None:
    assert near_context_limit(6600, 8192) is True  # 80,6% — предупреждение
    assert near_context_limit(4000, 8192) is False
    assert near_context_limit(0, 8192) is False
