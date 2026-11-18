"""Счётчик сообщений диалога не должен пересчитываться полным поиском."""

from __future__ import annotations

from unittest.mock import MagicMock

from ostis_ui_assistant.sc import dialog_store


def test_message_index_uses_in_memory_counter(monkeypatch) -> None:
    calls = 0

    def fake_search(*args, **kwargs):
        nonlocal calls
        calls += 1
        return []

    monkeypatch.setattr(dialog_store, "search_by_template", fake_search)
    monkeypatch.setattr(
        dialog_store, "ScKeynodes", {"nrel_ui_dialog_message": MagicMock()}
    )
    dialog_store.reset_counters()
    dialog = MagicMock()
    dialog.value = 12345
    dialog.is_valid.return_value = True

    assert dialog_store._message_index(dialog) == 1
    assert dialog_store._message_index(dialog) == 2
    assert dialog_store._message_index(dialog) == 3
    assert calls == 1  # поиск только при первом обращении к диалогу


def test_read_history_batches_queries(monkeypatch) -> None:
    """Число запросов к БЗ не растёт линейно с числом сообщений."""
    calls = 0

    class FakeAddr:
        def __init__(self, value: int) -> None:
            self.value = value

        def isValid(self) -> bool:
            return True

    class FakeRow:
        def __init__(self, index: int) -> None:
            self.index = index

        def get(self, alias: str):
            base = {
                "_message": 1,
                "_link": 100,
                "_source": 200,
                "_rrel": 300,
            }[alias]
            return FakeAddr(base + self.index)

    def fake_search(*args, **kwargs):
        nonlocal calls
        calls += 1
        return [FakeRow(index) for index in range(10)]

    monkeypatch.setattr(dialog_store, "search_by_template", fake_search)
    monkeypatch.setattr(dialog_store, "get_link_content_data", lambda addr: "значение")
    monkeypatch.setattr(
        dialog_store,
        "get_element_system_identifier",
        lambda addr: f"rrel_{addr.value - 299}" if addr.value >= 300 else "src",
    )
    monkeypatch.setattr(dialog_store, "ScKeynodes", {key: MagicMock() for key in (
        "nrel_ui_dialog_message", "nrel_ui_value", "nrel_ui_message_state",
        "nrel_ui_message_time", "nrel_ui_llm_model", "nrel_ui_prompt_version",
        "nrel_ui_knowledge_source", "nrel_ui_answer_source",
        "concept_ui_user_message", "concept_ui_assistant_message",
    )})

    history = dialog_store.read_history(MagicMock(value=42))

    assert len(history) == 10
    assert calls <= 12  # вместо ~10 запросов на каждое сообщение


def test_roles_above_ten_are_generated(monkeypatch) -> None:
    captured: list[str] = []

    class FakeKeynodes(dict):
        def rrel_index(self, index: int):
            return MagicMock(value=index)

        def resolve(self, idtf: str, node_type):
            captured.append(idtf)
            return MagicMock(value=11)

    monkeypatch.setattr(dialog_store, "ScKeynodes", FakeKeynodes())

    assert dialog_store._rrel(2).is_valid()
    assert dialog_store._rrel(11).is_valid()
    assert captured == ["rrel_11"]
