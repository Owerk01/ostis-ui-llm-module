"""Health из узла состояния сервиса."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterator

from ostis_ui_assistant.config import Settings
from ostis_ui_assistant.knowledge.service import KnowledgeService
from ostis_ui_assistant.llm.base import LLMStats
from ostis_ui_assistant.sc import service_state
from ostis_ui_assistant.sc.service_state import ServiceState


class DummyBackend:
    model = "dummy"

    def __init__(self) -> None:
        self.calls = 0

    def chat(
        self, messages: list[dict[str, str]], *, max_tokens: int | None = None
    ) -> Iterator[str]:
        self.calls += 1
        yield "Ответ."

    @property
    def last_stats(self) -> LLMStats:
        return LLMStats()

    def health(self) -> bool:
        return True


def _state_with(settings: Settings, state: str, *, knowledge_source: str = "kb") -> ServiceState:
    """Сервисный узел в заданном состоянии (без живого sc-подключения)."""
    instance = ServiceState(settings)
    instance._state = {
        "instance_id": instance.instance_id,
        "state": state,
        "heartbeat_at": service_state.now_iso(),
        "model": "qwen3.5:4b",
        "backend": "ollama",
        "prompt_version": "v4",
        "pack_version": "2026-11-18T00:00:00Z",
        "knowledge_source": knowledge_source,
        "contract_version": "0.1.0",
        "queue_capacity": 16,
        "queue_size": 0,
        "active_requests": 0,
        "pid": "0",
        "host": "test",
    }
    return instance


def test_health_from_service_node_ready(settings: Settings) -> None:
    """Агент запущен, сообщений нет: состояние берётся из узла сервиса."""
    state = _state_with(settings, "ready")
    service = KnowledgeService(
        settings.model_copy(update={"knowledge_source": "fallback"}),
        backend=DummyBackend(),
        state=state,
    )

    health = service.health()

    assert health["agentAlive"] is True
    assert health["state"] == "ready"
    assert health["model"] == "qwen3.5:4b"
    assert health["packVersion"] == "2026-11-18T00:00:00Z"
    assert health["promptVersion"] == "v4"
    assert health["knowledgeSource"] == "kb"
    assert health["queueDepth"] == 0
    assert health["contractVersion"] == "0.1.0"
    assert health["timeouts"]["llmTimeoutS"] == 25.0
    assert health["timeouts"]["dialogClientTimeoutS"] == 35.0


def test_health_agent_stopped_or_heartbeat_stale(settings: Settings) -> None:
    """Остановленный агент или протухший heartbeat → agentAlive=false."""
    stopped = _state_with(settings, "stopped")
    service_stopped = KnowledgeService(
        settings.model_copy(update={"knowledge_source": "fallback"}),
        backend=DummyBackend(),
        state=stopped,
    )
    assert service_stopped.health()["agentAlive"] is False

    stale = _state_with(settings, "ready")
    stale._state["heartbeat_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=120)
    ).isoformat().replace("+00:00", "Z")
    service_stale = KnowledgeService(
        settings.model_copy(update={"knowledge_source": "fallback"}),
        backend=DummyBackend(),
        state=stale,
    )
    assert service_stale.health()["agentAlive"] is False


def test_health_state_busy_when_queue_overflowed(settings: Settings) -> None:
    busy = _state_with(settings, "busy")
    busy._state["queue_size"] = 16
    service_busy = KnowledgeService(
        settings.model_copy(update={"knowledge_source": "fallback"}),
        backend=DummyBackend(),
        state=busy,
    )
    assert service_busy.health()["state"] == "busy"
    assert service_busy.health()["queueDepth"] == 16


def test_health_without_state_uses_settings_defaults(settings: Settings) -> None:
    service = KnowledgeService(
        settings.model_copy(update={"knowledge_source": "fallback"}),
        backend=DummyBackend(),
        state=None,
    )
    health = service.health()
    assert health["agentAlive"] is False
    assert health["state"] == "starting"
    assert (
        health["timeouts"]["dialogClientTimeoutS"] > health["timeouts"]["llmTimeoutS"]
    )
