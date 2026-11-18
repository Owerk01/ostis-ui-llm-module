"""OpenAI-совместимый бэкенд: смена провайдера только через .env."""

from __future__ import annotations

import logging
import time
from typing import Iterator

from ..config import Settings
from .base import LLMStats, LLMTimeout, LLMUnavailable

logger = logging.getLogger(__name__)

_WARNED_ABOUT_OLLAMA_OPTIONS = False


class OpenAIBackend:
    model: str

    def __init__(self, settings: Settings, client: object | None = None) -> None:
        global _WARNED_ABOUT_OLLAMA_OPTIONS

        from openai import OpenAI

        self.model = settings.llm_model
        self._temperature = settings.llm_temperature
        self._top_p = settings.llm_top_p
        self._max_tokens = settings.llm_max_output_tokens
        self._client = client or OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key or "not-needed",
            timeout=settings.llm_timeout_s,
        )
        self._last_stats = LLMStats()

        if not _WARNED_ABOUT_OLLAMA_OPTIONS:
            logger.warning(
                "LLM_BACKEND=openai: параметры LLM_NUM_CTX, LLM_THINK, "
                "LLM_KEEP_ALIVE игнорируются (они специфичны для Ollama)"
            )
            _WARNED_ABOUT_OLLAMA_OPTIONS = True

    @property
    def last_stats(self) -> LLMStats:
        return self._last_stats

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        from openai import APIConnectionError, APIError, APITimeoutError

        self._last_stats = LLMStats()
        started = time.perf_counter()
        usage_seen = False

        def create_stream(*, completion_key: str, include_usage: bool):
            params = dict(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=self._temperature,
                top_p=self._top_p,
            )
            params[completion_key] = max_tokens or self._max_tokens
            if include_usage:
                params["stream_options"] = {"include_usage": True}
            try:
                return self._client.chat.completions.create(**params)
            except APIError as exc:
                text = str(exc).lower()
                # Разные OpenAI-совместимые API принимают разные имена параметров.
                if include_usage and "stream_options" in text:
                    return create_stream(completion_key=completion_key, include_usage=False)
                if completion_key == "max_tokens" and (
                    "max_tokens" in text or "unsupported parameter" in text
                ):
                    return create_stream(
                        completion_key="max_completion_tokens", include_usage=include_usage
                    )
                raise

        try:
            stream = create_stream(completion_key="max_tokens", include_usage=True)
            for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    usage_seen = True
                    self._last_stats = LLMStats(
                        prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
                        output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
                        total_ms=(time.perf_counter() - started) * 1000,
                    )
                if not getattr(chunk, "choices", None):
                    continue
                piece = getattr(chunk.choices[0].delta, "content", None)
                if piece:
                    yield piece
            if not usage_seen:
                self._last_stats.tokens_unavailable = True
        except APITimeoutError as exc:
            raise LLMTimeout("Превышено время ожидания ответа OpenAI-совместимого API") from exc
        except APIConnectionError as exc:
            raise LLMUnavailable(f"LLM недоступна: {exc}") from exc
        except APIError as exc:
            raise LLMUnavailable(f"Ошибка LLM: {exc}") from exc
        finally:
            if self._last_stats.total_ms == 0:
                self._last_stats.total_ms = (time.perf_counter() - started) * 1000

    def health(self) -> bool:
        try:
            self._client.models.list()
            return True
        except Exception:  # SDK поднимает разные типы ошибок
            return False
