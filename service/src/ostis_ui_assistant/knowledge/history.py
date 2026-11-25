"""Подготовка истории диалога для промпта.

Это лишь последние N завершённых сообщений, а не долговременная память агента:
старые ходы отбрасываются, pending/ошибочные сообщения в промпт не попадают.
"""

from __future__ import annotations

from typing import Any, Iterable


def message_key(message: dict[str, Any]) -> str:
    value = message.get("scAddr")
    if value is None:
        value = message.get("id")
    return str(value) if value is not None else ""


def prepare_history(
    messages: Iterable[dict[str, Any]],
    limit: int,
    *,
    exclude_ids: Iterable[Any] = (),
) -> list[dict[str, str]]:
    """Возвращает последние `limit` user/assistant-сообщений в формате LLM.

    Исключаются текущий вопрос, pending-сообщения и ходы с пустым текстом.
    При `limit <= 0` история в промпт не добавляется.
    """
    if limit <= 0:
        return []
    excluded = {str(value) for value in exclude_ids}
    result: list[dict[str, str]] = []
    for message in messages:
        key = message_key(message)
        if key and key in excluded:
            continue
        role = message.get("role")
        if role not in ("user", "assistant"):
            continue
        # User-сообщения в БЗ имеют state=done; assistant — только после ответа.
        if str(message.get("state") or "done") != "done":
            continue
        if str(message.get("code") or "") == "pending":
            continue
        text = str(message.get("text") or "").strip()
        if not text:
            continue
        result.append({"role": role, "content": text})
    return result[-limit:]
