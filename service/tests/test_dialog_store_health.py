"""Источник знаний и модель в конструкциях диалога."""

from __future__ import annotations

from unittest.mock import MagicMock

from ostis_ui_assistant.sc import dialog_store


def test_append_assistant_message_writes_knowledge_source(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_append(*args, **kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(dialog_store, "_append_message", fake_append)
    dialog_store.append_assistant_message(
        MagicMock(),
        "ответ",
        "qwen3.5:4b",
        "v4|pack:2026-11-18T00:00:00Z",
        [],
        knowledge_source="fallback",
    )
    assert captured["knowledge_source"] == "fallback"
