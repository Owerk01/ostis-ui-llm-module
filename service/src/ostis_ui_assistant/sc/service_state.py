"""Состояние сервиса диалога и advisory-аренда единственного экземпляра.

B0-2: два процесса, подписанные на `action_initiated`, дают два ответа. Аренда
не является распределённой блокировкой: это договорённость «один экземпляр на
БЗ», подкреплённая heartbeat в sc-памяти. Узел состояния — сам keynode
`concept_ui_dialog_service`, поэтому в БЗ гарантированно один такой узел.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sc_client.client import search_by_template, set_link_contents
from sc_client.constants import sc_type
from sc_client.models import (
    ScAddr,
    ScLinkContent,
    ScLinkContentType,
    ScTemplate,
)
from sc_kpm import ScKeynodes
from sc_kpm.utils import generate_binary_relation, generate_link, get_link_content_data

from ..config import Settings

logger = logging.getLogger(__name__)

STATE_STARTING = "starting"
STATE_READY = "ready"
STATE_DEGRADED = "degraded"
STATE_STOPPING = "stopping"
STATE_STOPPED = "stopped"

# Версия контракта диалога, касающаяся текущего состояния сервиса (B0-5).
CONTRACT_VERSION = "0.1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def lease_is_live(
    state: dict[str, Any] | None,
    heartbeat_at: str | None,
    *,
    ttl_s: float,
    now: datetime | None = None,
) -> bool:
    """Свежий heartbeat и не «остановленное» состояние = другой экземпляр жив."""
    if not state or state.get("state") == STATE_STOPPED:
        return False
    moment = _parse_iso(heartbeat_at)
    if moment is None:
        return False
    current = now or datetime.now(timezone.utc)
    age = (current - moment).total_seconds()
    return 0 <= age <= ttl_s


class ServiceState:
    """Единственный узел состояния сервиса: heartbeat, аренда, поля health."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.instance_id = (
            f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        )
        self.node: ScAddr | None = None
        self._state: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._queue_size = 0
        self._active_requests = 0

    # --- аренда ---------------------------------------------------------

    def acquire(self) -> bool:
        """Занимает аренду или возвращает False, если жив другой экземпляр."""
        with self._lock:
            self.node = ScKeynodes["concept_ui_dialog_service"]
            state = self._read_state()
            heartbeat = self._read_heartbeat()
            if lease_is_live(
                state,
                heartbeat,
                ttl_s=self.settings.service_lease_ttl_s,
            ):
                logger.error(
                    "Агент уже запущен (instance %s, heartbeat %s), "
                    "второй экземпляр не допускается",
                    (state or {}).get("instance_id", "unknown"),
                    heartbeat,
                )
                return False

            self._state = {
                "instance_id": self.instance_id,
                "started_at": now_iso(),
                "heartbeat_at": now_iso(),
                "state": STATE_STARTING,
                "model": self.settings.llm_model,
                "backend": self.settings.llm_backend,
                "prompt_version": self.settings.prompt_version,
                "pack_version": None,
                "knowledge_source": None,
                "contract_version": CONTRACT_VERSION,
                "queue_capacity": self.settings.dialog_queue_size,
                "queue_size": 0,
                "active_requests": 0,
                "pid": os.getpid(),
                "host": socket.gethostname(),
            }
            self._ensure_link("nrel_ui_service_state", "{}")
            self._ensure_link("nrel_ui_service_heartbeat", self._state["heartbeat_at"])
            self._write_state()
            self._write_heartbeat()
            logger.info(
                "Аренда сервиса диалога занята: instance %s", self.instance_id
            )
            return True

    def release(self) -> None:
        """Корректная остановка: помечает аренду свободной."""
        with self._lock:
            if self.node is None:
                return
            self._state["state"] = STATE_STOPPED
            self._state["stopped_at"] = now_iso()
            self._state["heartbeat_at"] = now_iso()
            self._state["active_requests"] = 0
            self._write_state()
            self._write_heartbeat()
            logger.info("Аренда сервиса диалога освобождена: %s", self.instance_id)

    # --- heartbeat ------------------------------------------------------

    def start_heartbeat(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            name="dialog-service-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def stop_heartbeat(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _heartbeat_loop(self) -> None:
        interval = max(1.0, self.settings.service_heartbeat_interval_s)
        while not self._stop.wait(interval):
            self.update_load(self._queue_size, self._active_requests)
            with self._lock:
                if self.node is None or self._state.get("state") == STATE_STOPPED:
                    continue
                self._state["heartbeat_at"] = now_iso()
                self._write_state()
                self._write_heartbeat()

    def update_load(self, queue_size: int, active_requests: int) -> None:
        with self._lock:
            self._queue_size = max(0, queue_size)
            self._active_requests = max(0, active_requests)
            self._state["queue_size"] = self._queue_size
            self._state["active_requests"] = self._active_requests

    # --- состояние ------------------------------------------------------

    def set_state(self, state: str, **fields: Any) -> None:
        with self._lock:
            self._state["state"] = state
            self._state.update(fields)
            self._state["heartbeat_at"] = now_iso()
            self._write_state()
            self._write_heartbeat()

    def mark_ready(
        self,
        *,
        pack_version: str,
        knowledge_source: str,
        kb_partial: bool = False,
        kb_missing: list[str] | None = None,
    ) -> None:
        degraded = kb_partial or knowledge_source != "kb"
        self.set_state(
            STATE_DEGRADED if degraded else STATE_READY,
            pack_version=pack_version,
            knowledge_source=knowledge_source,
            kb_partial=kb_partial,
            kb_missing=kb_missing or [],
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    # --- sc-память ------------------------------------------------------

    def _read_state(self) -> dict[str, Any] | None:
        value = self._read_link("nrel_ui_service_state")
        if not value:
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            logger.warning("Некорректный JSON в nrel_ui_service_state")
            return None
        return parsed if isinstance(parsed, dict) else None

    def _read_heartbeat(self) -> str | None:
        return self._read_link("nrel_ui_service_heartbeat")

    def _read_link(self, relation: str) -> str | None:
        if self.node is None:
            return None
        templ = ScTemplate()
        templ.quintuple(
            self.node,
            sc_type.VAR_COMMON_ARC,
            sc_type.VAR_NODE_LINK >> "_link",
            sc_type.VAR_PERM_POS_ARC,
            ScKeynodes[relation],
        )
        rows = search_by_template(templ)
        if not rows:
            return None
        return str(get_link_content_data(rows[0].get("_link")))

    def _ensure_link(self, relation: str, initial: str) -> None:
        if self._find_link(relation) is not None:
            return
        assert self.node is not None
        link = generate_link(initial)
        generate_binary_relation(
            sc_type.CONST_COMMON_ARC, self.node, link, ScKeynodes[relation]
        )

    def _find_link(self, relation: str) -> ScAddr | None:
        if self.node is None:
            return None
        templ = ScTemplate()
        templ.quintuple(
            self.node,
            sc_type.VAR_COMMON_ARC,
            sc_type.VAR_NODE_LINK >> "_link",
            sc_type.VAR_PERM_POS_ARC,
            ScKeynodes[relation],
        )
        rows = search_by_template(templ)
        if not rows:
            return None
        return rows[0].get("_link")

    def _set_link(self, relation: str, value: str) -> None:
        link = self._find_link(relation)
        if link is None:
            self._ensure_link(relation, value)
            link = self._find_link(relation)
            if link is None:
                logger.warning("Не удалось создать sc-link для %s", relation)
                return
        set_link_contents(ScLinkContent(value, ScLinkContentType.STRING, link))

    def _write_state(self) -> None:
        self._set_link(
            "nrel_ui_service_state",
            json.dumps(self._state, ensure_ascii=False, sort_keys=True),
        )

    def _write_heartbeat(self) -> None:
        self._set_link("nrel_ui_service_heartbeat", self._state.get("heartbeat_at", now_iso()))
