"""Контрактные тесты LLM-бэкендов без сети.

Оба бэкенда проверяются одним набором ожиданий: поток кусков, статистика,
отображение ошибок. Живой прогон — в test_live_llm.py (маркер llm).
"""

from __future__ import annotations

import json

import httpx
import pytest

from ostis_ui_assistant.config import Settings
from ostis_ui_assistant.llm.base import LLMUnavailable, create_backend
from ostis_ui_assistant.llm.ollama_backend import OllamaBackend
from ostis_ui_assistant.llm.openai_backend import OpenAIBackend


def ollama_settings(**overrides) -> Settings:
    values = dict(
        llm_backend="ollama",
        llm_base_url="http://ollama.test:11434",
        llm_model="qwen3.5:4b",
        llm_num_ctx=8192,
        llm_temperature=0.2,
        llm_top_p=0.9,
        llm_think=False,
        llm_keep_alive="30m",
        llm_timeout_s=5,
        llm_max_output_tokens=256,
    )
    values.update(overrides)
    return Settings(**values)


def openai_settings(**overrides) -> Settings:
    values = dict(
        llm_backend="openai",
        llm_base_url="http://api.test/v1",
        llm_model="remote-model",
        llm_api_key="secret",
        llm_temperature=0.2,
        llm_top_p=0.9,
        llm_timeout_s=5,
        llm_max_output_tokens=256,
    )
    values.update(overrides)
    return Settings(**values)


def ndjson(*chunks: dict) -> bytes:
    return ("\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in chunks) + "\n").encode()


def ollama_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# --- Ollama ---------------------------------------------------------------


def test_ollama_streams_pieces_and_stats() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            content=ndjson(
                {"message": {"content": "Кнопка "}, "done": False},
                {"message": {"content": "— компонент."}, "done": False},
                {
                    "message": {"content": ""},
                    "done": True,
                    "prompt_eval_count": 2783,
                    "eval_count": 65,
                    "total_duration": 3_500_000_000,
                },
            ),
        )

    backend = OllamaBackend(ollama_settings(), http_client=ollama_client(handler))
    pieces = list(backend.chat([{"role": "user", "content": "вопрос"}]))

    assert pieces == ["Кнопка ", "— компонент."]
    assert backend.last_stats.prompt_tokens == 2783
    assert backend.last_stats.output_tokens == 65
    assert backend.last_stats.total_ms == pytest.approx(3500.0)

    assert captured["url"] == "http://ollama.test:11434/api/chat"
    payload = captured["payload"]
    assert payload["model"] == "qwen3.5:4b"
    assert payload["stream"] is True
    assert payload["think"] is False
    assert payload["keep_alive"] == "30m"
    assert payload["options"]["num_ctx"] == 8192
    assert payload["options"]["temperature"] == 0.2
    assert payload["options"]["top_p"] == 0.9
    assert payload["options"]["num_predict"] == 256


def test_ollama_skips_malformed_lines() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b'not-json\n{"message":{"content":"ok"},"done":true,"eval_count":1}\n',
        )

    backend = OllamaBackend(ollama_settings(), http_client=ollama_client(handler))
    assert list(backend.chat([{"role": "user", "content": "q"}])) == ["ok"]


def test_ollama_http_error_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "model not found"})

    backend = OllamaBackend(ollama_settings(), http_client=ollama_client(handler))
    with pytest.raises(LLMUnavailable):
        list(backend.chat([{"role": "user", "content": "q"}]))


def test_ollama_in_stream_error_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=ndjson({"error": "out of memory"}))

    backend = OllamaBackend(ollama_settings(), http_client=ollama_client(handler))
    with pytest.raises(LLMUnavailable):
        list(backend.chat([{"role": "user", "content": "q"}]))


def test_ollama_health_and_model_available() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:4b"}]})
        return httpx.Response(404)

    backend = OllamaBackend(ollama_settings(), http_client=ollama_client(handler))
    assert backend.health() is True
    assert backend.model_available() is True


def test_ollama_health_failure_is_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no connection", request=request)

    backend = OllamaBackend(ollama_settings(), http_client=ollama_client(handler))
    assert backend.health() is False


# --- OpenAI ---------------------------------------------------------------


class FakeDelta:
    def __init__(self, content: str | None) -> None:
        self.content = content


class FakeChoice:
    def __init__(self, content: str | None) -> None:
        self.delta = FakeDelta(content)


class FakeChunk:
    def __init__(self, content: str | None, usage=None) -> None:
        self.choices = [FakeChoice(content)] if content is not None else []
        self.usage = usage


class FakeUsage:
    prompt_tokens = 2700
    completion_tokens = 70


class FakeCompletions:
    def __init__(self, chunks: list[FakeChunk], captured: dict) -> None:
        self._chunks = chunks
        self._captured = captured

    def create(self, **kwargs):
        self._captured.update(kwargs)
        return iter(self._chunks)


class FakeChat:
    def __init__(self, chunks: list[FakeChunk], captured: dict) -> None:
        self.completions = FakeCompletions(chunks, captured)


class FakeOpenAIClient:
    def __init__(self, chunks: list[FakeChunk], captured: dict | None = None) -> None:
        self.captured = captured if captured is not None else {}
        self.chat = FakeChat(chunks, self.captured)


def test_openai_streams_pieces_and_stats() -> None:
    captured: dict = {}
    client = FakeOpenAIClient(
        [FakeChunk("Кнопка "), FakeChunk("— компонент.", usage=FakeUsage())],
        captured,
    )
    backend = OpenAIBackend(openai_settings(), client=client)
    pieces = list(backend.chat([{"role": "user", "content": "q"}]))

    assert pieces == ["Кнопка ", "— компонент."]
    assert backend.last_stats.prompt_tokens == 2700
    assert backend.last_stats.output_tokens == 70
    assert captured["model"] == "remote-model"
    assert captured["stream"] is True
    assert captured["temperature"] == 0.2
    assert captured["top_p"] == 0.9
    assert "num_ctx" not in captured


def test_openai_connection_error_is_unavailable() -> None:
    import openai

    class FailingCompletions:
        def create(self, **kwargs):
            raise openai.APIConnectionError(request=httpx.Request("POST", "http://api.test"))

    class FailingChat:
        completions = FailingCompletions()

    class FailingClient:
        chat = FailingChat()

    backend = OpenAIBackend(openai_settings(), client=FailingClient())
    with pytest.raises(LLMUnavailable):
        list(backend.chat([{"role": "user", "content": "q"}]))


def test_stats_reset_on_error() -> None:
    """После ошибки в журнал не должны попасть токены предыдущего запроса."""
    from ostis_ui_assistant.llm.base import LLMStats, LLMTimeout

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    backend = OllamaBackend(ollama_settings(), http_client=ollama_client(handler))
    backend._last_stats = LLMStats(prompt_tokens=999, output_tokens=888, total_ms=777)

    with pytest.raises(LLMTimeout):
        list(backend.chat([{"role": "user", "content": "q"}]))

    assert backend.last_stats.prompt_tokens == 0
    assert backend.last_stats.output_tokens == 0


def test_openai_requests_usage_and_limit_param() -> None:
    captured: dict = {}
    client = FakeOpenAIClient([FakeChunk("ok", usage=FakeUsage())], captured)
    backend = OpenAIBackend(openai_settings(), client=client)
    list(backend.chat([{"role": "user", "content": "q"}]))

    assert captured["stream_options"] == {"include_usage": True}
    assert captured["max_tokens"] == 256


def test_openai_without_usage_marks_tokens_unavailable() -> None:
    client = FakeOpenAIClient([FakeChunk("ok")])
    backend = OpenAIBackend(openai_settings(), client=client)
    list(backend.chat([{"role": "user", "content": "q"}]))

    assert backend.last_stats.tokens_unavailable is True


# --- Фабрика --------------------------------------------------------------


def test_create_backend_selects_by_env() -> None:
    assert isinstance(create_backend(ollama_settings()), OllamaBackend)
    assert isinstance(create_backend(openai_settings()), OpenAIBackend)
