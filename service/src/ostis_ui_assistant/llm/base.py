"""Общий контракт LLM-бэкенда.

Бэкенд отдаёт поток текстовых фрагментов. Специфичные для Ollama параметры
(num_ctx, keep_alive, think) в OpenAI-совместимом бэкенде игнорируются.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol

from ..config import Settings


class LLMError(RuntimeError):
    """Базовая ошибка LLM."""


class LLMUnavailable(LLMError):
    """LLM недоступна (нет соединения, ошибка сервера)."""


class LLMTimeout(LLMError):
    """Превышено время ожидания ответа."""


@dataclass
class LLMStats:
    prompt_tokens: int = 0
    output_tokens: int = 0
    total_ms: float = 0.0


class LLMBackend(Protocol):
    model: str

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Возвращает поток текстовых фрагментов ответа."""

    @property
    def last_stats(self) -> LLMStats:
        """Статистика последнего завершённого запроса."""

    def health(self) -> bool:
        """Проверка доступности провайдера (без генерации)."""


def create_backend(settings: Settings) -> LLMBackend:
    if settings.llm_backend == "ollama":
        from .ollama_backend import OllamaBackend

        return OllamaBackend(settings)

    from .openai_backend import OpenAIBackend

    return OpenAIBackend(settings)
