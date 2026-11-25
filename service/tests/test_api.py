"""Тесты direct-http API: /health, /ask SSE, /cancel."""

from __future__ import annotations

import json
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from ostis_ui_assistant.api.app import create_app
from ostis_ui_assistant.knowledge.service import AnswerResult, Cancelled
from ostis_ui_assistant.llm.base import LLMTimeout, LLMUnavailable


class FakeService:
    def __init__(self, *, text: str = "Ответ ассистента.", mode: str = "ok") -> None:
        self.text = text
        self.mode = mode
        self.questions: list[str] = []
        self.closed = False

    def answer(self, question: str, cancel_event=None) -> AnswerResult:
        self.questions.append(question)
        if self.mode == "unavailable":
            raise LLMUnavailable("нет соединения")
        if self.mode == "timeout":
            raise LLMTimeout("таймаут")
        if self.mode == "cancelled":
            raise Cancelled
        if self.mode == "internal":
            raise RuntimeError("сбой")
        return AnswerResult(
            text=self.text,
            model="qwen3.5:4b",
            prompt_version="v1",
            pack_version="2026-11-17T15:12:47Z",
            sources=[{"idtf": "concept_ui_button", "labelRu": "Кнопка"}],
            prompt_tokens=2783,
            output_tokens=65,
            latency_ms=3543.3,
        )

    def health(self) -> dict[str, Any]:
        return {
            "llm": {"backend": "ollama", "model": "qwen3.5:4b", "reachable": True},
            "kb": {
                "connected": False,
                "knowledgeSource": "fallback",
                "packVersion": "2026-11-17T15:12:47Z",
            },
            "sc_connected": False,
            "knowledge_source": "fallback",
            "pack_version": "2026-11-17T15:12:47Z",
            "prompt_version": "v1",
        }

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def client(settings):
    app = create_app(settings, service=FakeService())
    with TestClient(app) as test_client:
        yield test_client


def parse_sse(lines: Iterator[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    event_name = ""
    for line in lines:
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = json.loads(line.split(":", 1)[1].strip())
            events.append({"event": event_name, "data": data})
    return events


def ask(client: TestClient, question: str = "Что такое concept_ui_button?") -> list[dict[str, Any]]:
    with client.stream("POST", "/ask", json={"question": question}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return parse_sse(response.iter_lines())


def test_health_reports_fallback_and_pack(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["knowledge_source"] == "fallback"
    assert body["kb"]["knowledgeSource"] == "fallback"
    assert body["pack_version"]


def test_ask_streams_meta_delta_done(client: TestClient) -> None:
    events = ask(client)
    names = [event["event"] for event in events]
    assert names[0] == "meta"
    assert names[-1] == "done"
    assert "delta" in names

    meta = events[0]["data"]
    assert meta["state"] == "pending"
    assert meta["code"] == "pending"
    assert meta["message_id"]
    assert meta["dialog_id"]

    text = "".join(e["data"]["text"] for e in events if e["event"] == "delta")
    assert text == "Ответ ассистента."

    done = events[-1]["data"]
    assert done["message"]["state"] == "done"
    assert done["message"]["text"] == "Ответ ассистента."
    assert done["message"]["sources"] == [
        {"idtf": "concept_ui_button", "labelRu": "Кнопка"}
    ]
    assert done["prompt_version"] == "v1"
    assert done["pack_version"]


def test_ask_saves_history(client: TestClient) -> None:
    events = ask(client, "вопрос")
    dialog_id = events[0]["data"]["dialog_id"]

    history = client.get(f"/history/{dialog_id}").json()
    assert [item["role"] for item in history] == ["user", "assistant"]
    assert history[0]["text"] == "вопрос"
    assert history[1]["state"] == "done"
    assert history[1]["code"] == "ok"


def test_ask_rejects_empty_question(client: TestClient) -> None:
    assert client.post("/ask", json={"question": ""}).status_code == 422
    response = client.post("/ask", json={"question": "   "})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_request"


def test_ask_reports_llm_unavailable(settings) -> None:
    app = create_app(settings, service=FakeService(mode="unavailable"))
    with TestClient(app) as test_client:
        events = ask(test_client)
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "llm_unavailable"
    assert "Ollama" in events[-1]["data"]["error"]
    history = test_client.get(f"/history/{events[0]['data']['dialog_id']}").json()
    assert history[1]["code"] == "llm_unavailable"


def test_ask_reports_timeout(settings) -> None:
    app = create_app(settings, service=FakeService(mode="timeout"))
    with TestClient(app) as test_client:
        events = ask(test_client)
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "llm_timeout"
    assert "время ожидания" in events[-1]["data"]["error"]
    history = test_client.get(f"/history/{events[0]['data']['dialog_id']}").json()
    assert history[1]["code"] == "llm_timeout"


def test_ask_reports_internal_error_code(settings) -> None:
    app = create_app(settings, service=FakeService(mode="internal"))
    with TestClient(app) as test_client:
        events = ask(test_client)
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "internal"


def test_ask_reports_cancelled(settings) -> None:
    app = create_app(settings, service=FakeService(mode="cancelled"))
    with TestClient(app) as test_client:
        events = ask(test_client)
    assert events[-1]["event"] == "cancelled"
    assert events[-1]["data"]["message"]["state"] == "cancelled"
    assert events[-1]["data"]["message"]["code"] == "cancelled"


def test_cancel_unknown_message_returns_false(client: TestClient) -> None:
    response = client.post("/cancel", json={"message_id": "msg-unknown"})
    assert response.status_code == 200
    assert response.json()["cancelled"] is False


def test_cancel_registered_message_returns_true(client: TestClient) -> None:
    app = client.app
    event = app.state.cancels.create("msg-1")
    response = client.post("/cancel", json={"message_id": "msg-1"})
    assert response.json()["cancelled"] is True
    assert event.is_set()


def test_dialog_endpoint_creates_dialog(client: TestClient) -> None:
    response = client.post("/dialog")
    assert response.status_code == 200
    dialog_id = response.json()["dialog_id"]
    assert dialog_id.startswith("dlg-")
    assert client.get(f"/history/{dialog_id}").json() == []


def test_dialog_exists_endpoint_reports_created_dialog(client: TestClient) -> None:
    response = client.post("/dialog")
    assert response.status_code == 200
    dialog_id = response.json()["dialog_id"]
    assert client.get(f"/dialog/{dialog_id}").json()["exists"] is True


def test_dialog_exists_endpoint_reports_unknown_dialog(client: TestClient) -> None:
    assert client.get("/dialog/dlg-unknown-not-exist").json()["exists"] is False


def test_ask_unknown_dialog_returns_not_found(client: TestClient) -> None:
    """`ask` не должен подменять диалог: неизвестный id — ошибка `dialog_not_found`."""
    response = client.post(
        "/ask",
        json={"question": "Что такое concept_ui_button?", "dialog_id": "dlg-unknown-not-exist"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "dialog_not_found"


def test_stream_split_preserves_text() -> None:
    from ostis_ui_assistant.api.sse import split_for_stream

    text = "Слово " * 60
    chunks = split_for_stream(text.strip(), chunk_size=40)
    assert "".join(chunks).replace(" ", "") == text.strip().replace(" ", "")
    assert all(len(chunk) <= 41 for chunk in chunks)
