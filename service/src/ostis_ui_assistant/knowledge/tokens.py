"""Калибровка оценки токенов по фактическому размеру промпта."""

from __future__ import annotations

CONTEXT_WARNING_RATIO = 0.8


def near_context_limit(actual_tokens: int, num_ctx: int) -> bool:
    """True, если фактический промпт занимает >80% контекста модели."""
    if num_ctx <= 0 or actual_tokens <= 0:
        return False
    return actual_tokens / num_ctx > CONTEXT_WARNING_RATIO
