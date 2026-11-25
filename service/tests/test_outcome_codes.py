"""Машиночитаемые коды исхода и правило повтора."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ostis_ui_assistant.sc import dialog_store
from ostis_ui_assistant.sc.outcomes import (
    DEFAULT_CODE,
    MESSAGE_CODES,
    OUTCOME_CODES,
    PENDING_CODE,
    RETRYABLE_CODES,
    is_retryable,
    normalize_code,
)

CONTRACT = json.loads(
    (Path(__file__).resolve().parents[2] / "contract" / "identifiers.json").read_text(
        encoding="utf-8"
    )
)


def test_contract_lists_all_outcome_codes() -> None:
    assert CONTRACT["relation"] == "nrel_ui_message_code"
    assert CONTRACT["outcomeCodes"] == list(OUTCOME_CODES)
    assert CONTRACT["pendingCode"] == PENDING_CODE
    assert CONTRACT["defaultCode"] == DEFAULT_CODE
    assert set(CONTRACT["retryableCodes"]) == RETRYABLE_CODES


@pytest.mark.parametrize("code", OUTCOME_CODES)
def test_every_contract_code_is_written_to_message(code: str, monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        dialog_store,
        "_append_message",
        lambda *args, **kwargs: captured.update(kwargs) or MagicMock(),
    )

    dialog_store.append_error_message(MagicMock(), "ошибка", code=code)

    assert captured["code"] == code


def test_unknown_code_is_rejected() -> None:
    with pytest.raises(ValueError, match="Неизвестный код"):
        dialog_store.complete_assistant_message(MagicMock(), "ответ", code="unknown")


def test_default_codes_for_new_and_old_messages(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        dialog_store,
        "_append_message",
        lambda *args, **kwargs: captured.update(kwargs) or MagicMock(),
    )
    dialog_store.append_assistant_message(MagicMock(), "", "model", "v4")
    assert captured["code"] == PENDING_CODE

    complete = MagicMock()
    monkeypatch.setattr(dialog_store, "_set_link_value", complete)
    message = MagicMock()
    dialog_store.complete_assistant_message(message, "ответ")
    assert {call.args[1] for call in complete.call_args_list} >= {
        "nrel_ui_value",
        "nrel_ui_message_code",
    }
    assert ("nrel_ui_message_code", DEFAULT_CODE) in {
        (call.args[1], call.args[2]) for call in complete.call_args_list
    }

    assert normalize_code(None) == DEFAULT_CODE
    assert normalize_code("llm_timeout") == "llm_timeout"
    assert normalize_code("bogus") == DEFAULT_CODE


def test_retryable_comes_from_code() -> None:
    assert is_retryable("busy") is True
    assert is_retryable("llm_unavailable") is True
    assert is_retryable("llm_timeout") is True
    assert is_retryable("agent_restarted") is True
    assert is_retryable("internal") is True
    for code in ("ok", "invalid_request", "cancelled", "schema_missing", PENDING_CODE):
        assert is_retryable(code) is False

    assert set(MESSAGE_CODES) == set(OUTCOME_CODES) | {PENDING_CODE}
