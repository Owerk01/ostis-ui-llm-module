"""Память диалога и реестр отмен для direct-http (M1-T5/T6)."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DialogMessage:
    id: str
    role: str
    text: str
    state: str
    created_at: str
    sources: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "text": self.text,
            "state": self.state,
            "createdAt": self.created_at,
            "sources": self.sources,
            "error": self.error,
        }


class DialogStore:
    """In-memory история для отладочного транспорта; в sc-память пишет M2."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._dialogs: dict[str, list[DialogMessage]] = {}

    def create_dialog(self) -> str:
        dialog_id = f"dlg-{uuid.uuid4()}"
        with self._lock:
            self._dialogs[dialog_id] = []
        return dialog_id

    def ensure_dialog(self, dialog_id: str | None) -> str:
        if not dialog_id:
            return self.create_dialog()
        with self._lock:
            self._dialogs.setdefault(dialog_id, [])
        return dialog_id

    def history(self, dialog_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [message.to_dict() for message in self._dialogs.get(dialog_id, [])]

    def add_user_message(self, dialog_id: str, text: str) -> DialogMessage:
        message = DialogMessage(
            id=f"msg-{uuid.uuid4()}",
            role="user",
            text=text,
            state="done",
            created_at=utc_now(),
        )
        with self._lock:
            self._dialogs.setdefault(dialog_id, []).append(message)
        return message

    def add_assistant_pending(self, dialog_id: str) -> DialogMessage:
        message = DialogMessage(
            id=f"msg-{uuid.uuid4()}",
            role="assistant",
            text="",
            state="pending",
            created_at=utc_now(),
        )
        with self._lock:
            self._dialogs.setdefault(dialog_id, []).append(message)
        return message

    def update_assistant(
        self,
        dialog_id: str,
        message_id: str,
        *,
        text: str | None = None,
        state: str | None = None,
        sources: list[dict[str, str]] | None = None,
        error: str | None = None,
    ) -> DialogMessage | None:
        with self._lock:
            for message in self._dialogs.get(dialog_id, []):
                if message.id != message_id:
                    continue
                if text is not None:
                    message.text = text
                if state is not None:
                    message.state = state
                if sources is not None:
                    message.sources = sources
                if error is not None:
                    message.error = error
                return message
        return None


class CancelRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, threading.Event] = {}

    def create(self, message_id: str) -> threading.Event:
        event = threading.Event()
        with self._lock:
            self._events[message_id] = event
        return event

    def cancel(self, message_id: str) -> bool:
        with self._lock:
            event = self._events.get(message_id)
        if event is None:
            return False
        event.set()
        return True

    def remove(self, message_id: str) -> None:
        with self._lock:
            self._events.pop(message_id, None)


def sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def split_for_stream(text: str, chunk_size: int = 80) -> list[str]:
    """Режет уже провалидированный текст на куски по границам слов."""
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if len(candidate) > chunk_size and current:
            chunks.append(current + " ")
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
