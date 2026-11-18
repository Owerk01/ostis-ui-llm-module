"""Диалог имеет стабильный строковый идентификатор в БЗ."""

from __future__ import annotations

from unittest.mock import MagicMock

from ostis_ui_assistant.sc import dialog_store


def test_create_dialog_writes_nrel_ui_id(monkeypatch) -> None:
    links: list[str] = []
    relations: list[str] = []

    monkeypatch.setattr(dialog_store, "generate_node", lambda *a, **kw: MagicMock(value=1))
    monkeypatch.setattr(dialog_store, "generate_connector", lambda *a, **kw: MagicMock())
    monkeypatch.setattr(
        dialog_store,
        "generate_link",
        lambda content, *a, **kw: links.append(content) or MagicMock(value=2),
    )
    monkeypatch.setattr(
        dialog_store,
        "generate_binary_relation",
        lambda *a, **kw: relations.append(str(getattr(a[3], "value", a[3]))),
    )
    monkeypatch.setattr(
        dialog_store,
        "ScKeynodes",
        {"concept_ui_dialog": MagicMock(), "nrel_ui_id": MagicMock(value=777)},
    )

    dialog_store.create_dialog()

    assert relations
    assert links and links[0].startswith("dialog-")
