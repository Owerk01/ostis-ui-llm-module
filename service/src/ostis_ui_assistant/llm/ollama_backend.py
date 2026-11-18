"""Нативный Ollama-бэкенд: /api/chat, стрим, think:false."""

from __future__ import annotations

import json
import time
from typing import Iterator

import httpx

from ..config import Settings
from .base import LLMStats, LLMTimeout, LLMUnavailable


class OllamaBackend:
    model: str

    def __init__(self, settings: Settings, http_client: httpx.Client | None = None) -> None:
        self.model = settings.llm_model
        self._base_url = settings.llm_base_url.rstrip("/")
        self._url = f"{self._base_url}/api/chat"
        self._num_ctx = settings.llm_num_ctx
        self._temperature = settings.llm_temperature
        self._top_p = settings.llm_top_p
        self._think = settings.llm_think
        self._keep_alive = settings.llm_keep_alive
        self._max_tokens = settings.llm_max_output_tokens
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            timeout=httpx.Timeout(settings.llm_timeout_s, connect=5.0)
        )
        self._last_stats = LLMStats()

    @property
    def last_stats(self) -> LLMStats:
        return self._last_stats

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        payload = {
            "model": self.model,
            "stream": True,
            "think": self._think,
            "keep_alive": self._keep_alive,
            "options": {
                "num_ctx": self._num_ctx,
                "temperature": self._temperature,
                "top_p": self._top_p,
                "num_predict": max_tokens or self._max_tokens,
            },
            "messages": messages,
        }

        # Сбрасываем статистику до запроса: при ошибке в журнал не попадут
        # токены предыдущего ответа.
        self._last_stats = LLMStats()
        started = time.perf_counter()
        try:
            with self._client.stream("POST", self._url, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if chunk.get("error"):
                        raise LLMUnavailable(str(chunk["error"]))

                    piece = (chunk.get("message") or {}).get("content", "")
                    if piece:
                        yield piece

                    if chunk.get("done"):
                        self._last_stats = LLMStats(
                            prompt_tokens=int(chunk.get("prompt_eval_count") or 0),
                            output_tokens=int(chunk.get("eval_count") or 0),
                            total_ms=float(chunk.get("total_duration") or 0) / 1e6,
                        )
                        return
        except httpx.TimeoutException as exc:
            raise LLMTimeout("Превышено время ожидания ответа Ollama") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Ollama недоступна: {exc}") from exc
        finally:
            if self._last_stats.total_ms == 0:
                self._last_stats.total_ms = (time.perf_counter() - started) * 1000

    def health(self) -> bool:
        try:
            response = self._client.get(f"{self._base_url}/api/tags", timeout=3.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def model_available(self) -> bool:
        try:
            response = self._client.get(f"{self._base_url}/api/tags", timeout=3.0)
            if response.status_code != 200:
                return False
            names = {item.get("name", "") for item in response.json().get("models", [])}
            return self.model in names
        except (httpx.HTTPError, ValueError):
            return False

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
