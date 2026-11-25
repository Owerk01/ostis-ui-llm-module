"""Watchdog оформляет висячие действия кодом agent_restarted."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from ostis_ui_assistant.agents import watchdog
from ostis_ui_assistant.sc.outcomes import is_retryable


def test_watchdog_writes_agent_restarted(monkeypatch) -> None:
    action = MagicMock(value=101)
    message = MagicMock(value=102)
    monkeypatch.setattr(watchdog, "_orphan_actions", lambda: [action])
    monkeypatch.setattr(watchdog.dialog_store, "find_assistant_message", lambda _: message)
    monkeypatch.setattr(watchdog.dialog_store, "message_time", lambda _: None)
    complete = MagicMock()
    monkeypatch.setattr(watchdog.dialog_store, "complete_assistant_message", complete)
    finish = MagicMock()
    monkeypatch.setattr(watchdog, "finish_action_with_status", finish)

    closed = watchdog.close_orphan_actions(
        SimpleNamespace(watchdog_max_age_minutes=10)
    )

    assert closed == 1
    assert complete.call_args.args[0] is message
    code = complete.call_args.kwargs["code"]
    assert code == "agent_restarted"
    assert is_retryable(code) is True
    finish.assert_called_once_with(action, False)
