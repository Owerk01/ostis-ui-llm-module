"""Версия контракта: один источник в корневом VERSION."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from ostis_ui_assistant.config import Settings
from ostis_ui_assistant.sc import service_state
from ostis_ui_assistant.sc.service_state import (
    CONTRACT_VERSION,
    ServiceState,
    prompt_version_with_contract,
)

ROOT = Path(__file__).resolve().parents[2]


def test_contract_version_matches_root_version() -> None:
    assert CONTRACT_VERSION == (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_prompt_version_carries_contract_and_pack() -> None:
    assert prompt_version_with_contract("v4", "2026-11-18T00:00:00Z") == (
        f"v4|contract:{CONTRACT_VERSION}|pack:2026-11-18T00:00:00Z"
    )
    assert prompt_version_with_contract("v4") == f"v4|contract:{CONTRACT_VERSION}"


def test_service_state_node_publishes_contract_version(
    settings: Settings, monkeypatch
) -> None:
    monkeypatch.setattr(
        service_state, "ScKeynodes", {"concept_ui_dialog_service": MagicMock()}
    )
    state = ServiceState(settings)
    monkeypatch.setattr(state, "_read_state", lambda: None)
    monkeypatch.setattr(state, "_read_heartbeat", lambda: None)
    monkeypatch.setattr(state, "_ensure_link", MagicMock())
    monkeypatch.setattr(state, "_write_state", MagicMock())
    monkeypatch.setattr(state, "_write_heartbeat", MagicMock())

    assert state.acquire() is True
    assert state._state["contract_version"] == CONTRACT_VERSION
    assert f"contract:{CONTRACT_VERSION}" in state._state["prompt_version"]
