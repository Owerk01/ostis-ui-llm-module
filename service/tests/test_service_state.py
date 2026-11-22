"""B0-2: аренда единственного экземпляра по heartbeat в БЗ."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from ostis_ui_assistant.sc import service_state
from ostis_ui_assistant.sc.service_state import ServiceState, lease_is_live


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_live_heartbeat_means_another_instance() -> None:
    assert lease_is_live(
        {"instance_id": "other", "state": "ready"},
        _now(),
        ttl_s=20,
    )


def test_stale_or_stopped_lease_is_free() -> None:
    old = (datetime.now(timezone.utc) - timedelta(seconds=100)).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    assert not lease_is_live({"state": "ready"}, old, ttl_s=20)
    assert not lease_is_live({"state": "stopped"}, _now(), ttl_s=20)
    assert not lease_is_live(None, _now(), ttl_s=20)
    assert not lease_is_live({"state": "ready"}, None, ttl_s=20)


def test_second_instance_refuses_live_lease(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        service_state, "ScKeynodes", {"concept_ui_dialog_service": MagicMock()}
    )
    state = ServiceState(settings)
    monkeypatch.setattr(
        state, "_read_state", lambda: {"instance_id": "other", "state": "ready"}
    )
    monkeypatch.setattr(state, "_read_heartbeat", _now)
    writes = MagicMock()
    monkeypatch.setattr(state, "_write_state", writes)
    monkeypatch.setattr(state, "_write_heartbeat", MagicMock())

    assert state.acquire() is False
    writes.assert_not_called()


def test_stale_lease_is_taken_over(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        service_state, "ScKeynodes", {"concept_ui_dialog_service": MagicMock()}
    )
    state = ServiceState(settings)
    monkeypatch.setattr(
        state, "_read_state", lambda: {"instance_id": "old", "state": "ready"}
    )
    monkeypatch.setattr(
        state,
        "_read_heartbeat",
        lambda: (datetime.now(timezone.utc) - timedelta(seconds=100))
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
    )
    writes = MagicMock()
    monkeypatch.setattr(state, "_write_state", writes)
    monkeypatch.setattr(state, "_write_heartbeat", MagicMock())
    monkeypatch.setattr(state, "_ensure_link", MagicMock())

    assert state.acquire() is True
    assert writes.called
    assert state.snapshot()["instance_id"] == state.instance_id
