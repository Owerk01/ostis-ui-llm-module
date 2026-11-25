"""Машиночитаемые коды исхода assistant-сообщений.

Значения пишутся в `nrel_ui_message_code`; `pending` — служебный код для
ещё не завершённого сообщения, остальные — финальные исходы.
"""

from __future__ import annotations

OUTCOME_CODES: tuple[str, ...] = (
    "ok",
    "busy",
    "llm_unavailable",
    "llm_timeout",
    "invalid_request",
    "cancelled",
    "agent_restarted",
    "schema_missing",
    "schema_mismatch",
    "dialog_not_found",
    "internal",
)

PENDING_CODE = "pending"
DEFAULT_CODE = "ok"
MESSAGE_CODES: tuple[str, ...] = OUTCOME_CODES + (PENDING_CODE,)

# Временные ошибки, которые имеет смысл повторить без изменения вопроса.
RETRYABLE_CODES: frozenset[str] = frozenset(
    {
        "busy",
        "llm_unavailable",
        "llm_timeout",
        "agent_restarted",
        "internal",
    }
)


def is_retryable(code: str) -> bool:
    return code in RETRYABLE_CODES


def normalize_code(value: str | None, default: str = DEFAULT_CODE) -> str:
    """Старые сообщения без link и битые значения читаются как `ok`."""
    return value if value in MESSAGE_CODES else default
