"""Общие фикстуры тестов сервиса."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ostis_ui_assistant.config import Settings

ROOT = Path(__file__).resolve().parents[2]
PACK_PATH = ROOT / "knowledge" / "pack.json"
PROMPT_PATH = ROOT / "knowledge" / "prompt_v3.md"


@pytest.fixture(scope="session")
def settings(tmp_path_factory: pytest.TempPathFactory) -> Settings:
    logs = tmp_path_factory.mktemp("logs")
    return Settings(
        llm_backend="ollama",
        llm_base_url="http://127.0.0.1:11434",
        llm_model="qwen3.5:4b",
        knowledge_pack_path=PACK_PATH,
        prompt_path=PROMPT_PATH,
        dialog_log_path=logs / "dialog.jsonl",
    )


@pytest.fixture(scope="session")
def pack() -> dict[str, Any]:
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")
