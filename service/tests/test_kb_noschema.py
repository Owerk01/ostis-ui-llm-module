"""Интеграционный тест: чтение знаний не создаёт узлы чужой схемы."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.kb_noschema
def test_no_foreign_nodes_created() -> None:
    """БЗ собрана только из kb/ui_assistant, схемы UI нет.

    Запускать после `make kb-load-noschema` с RUN_NOSCHEMA_TEST=1.
    """
    if os.environ.get("RUN_NOSCHEMA_TEST") != "1":
        pytest.skip("нужна БЗ без схемы UI: make kb-load-noschema")

    from sc_client import client
    from sc_kpm import ScKeynodes

    from ostis_ui_assistant.knowledge import kb_reader

    url = os.environ.get("SC_WS_URL", "ws://127.0.0.1:8090/ws_json")
    if not client.is_connected():
        client.connect(url)
    pack = json.loads((ROOT / "knowledge" / "pack.json").read_text(encoding="utf-8"))
    assert not ScKeynodes.get("concept_ui_button").is_valid()
    assert not ScKeynodes.get("concept_ui_visible").is_valid()
    try:
        result, status = kb_reader.load_pack_from_kb(pack, url)
        assert result is not None
        assert status.source in {"kb", "fallback"}
        assert not ScKeynodes.get("concept_ui_button").is_valid()
        assert not ScKeynodes.get("concept_ui_visible").is_valid()
    finally:
        kb_reader.close()
