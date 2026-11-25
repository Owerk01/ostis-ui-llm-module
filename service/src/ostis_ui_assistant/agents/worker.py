"""Очередь и воркеры обработки вопросов (B0-1).

`UiDialogAgent.on_event` только принимает запрос и кладёт его в ограниченную
очередь. Генерация LLM выполняется здесь, поэтому поток событий sc-machine
освобождается сразу и предпросмотр редактора не ждёт наш ответ.
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sc_client.models import ScAddr
from sc_kpm import ScKeynodes
from sc_kpm.utils.action_utils import finish_action_with_status

from ..config import Settings
from ..knowledge.identifiers import PROPERTY_KEYS
from ..knowledge.instance import InstanceContext, read_context
from ..knowledge.service import Cancelled, KnowledgeService
from ..llm.base import LLMTimeout, LLMUnavailable
from ..sc import dialog_store
from ..sc import keynodes as kn
from ..sc.outcomes import DEFAULT_CODE

if TYPE_CHECKING:
    from ..sc.service_state import ServiceState

logger = logging.getLogger(__name__)

ERROR_MESSAGES = {
    LLMUnavailable: "Языковая модель недоступна. Проверьте, что Ollama запущена",
    LLMTimeout: "Превышено время ожидания ответа",
}

BUSY_MESSAGE = "Сервис занят: очередь запросов переполнена. Повторите вопрос позже."


@dataclass(slots=True)
class DialogJob:
    action: ScAddr
    dialog: ScAddr
    question: str
    message: ScAddr
    # rrel_3: узел контекста. Читается воркером, не в потоке событий sc-machine.
    context: Any = None


class DialogWorker:
    """Ограниченная очередь + 1–2 воркера генерации."""

    def __init__(
        self,
        service: KnowledgeService,
        settings: Settings,
        state: "ServiceState | None" = None,
    ) -> None:
        self._service = service
        self._settings = settings
        self._state = state
        self._queue: queue.Queue[DialogJob] = queue.Queue(
            maxsize=max(1, settings.dialog_queue_size)
        )
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._active = 0
        self._active_lock = threading.Lock()

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def active_requests(self) -> int:
        return self._active

    def start(self) -> None:
        count = max(1, min(2, self._settings.dialog_worker_threads))
        for index in range(count):
            thread = threading.Thread(
                target=self._run,
                name=f"dialog-worker-{index + 1}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)
        logger.info("Запущено воркеров диалога: %s, очередь %s", count, self._queue.maxsize)

    def submit(self, job: DialogJob) -> bool:
        try:
            self._queue.put_nowait(job)
        except queue.Full:
            return False
        self._sync_load()
        return True

    def stop(self, timeout: float = 2.0) -> None:
        """Останавливает приём и закрывает ещё не начатые запросы."""
        self._stop.set()
        while True:
            try:
                job = self._queue.get_nowait()
            except queue.Empty:
                break
            self._abort_job(job, "Агент остановлен до начала обработки", "agent_restarted")
            self._queue.task_done()
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()
        self._sync_load()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            with self._active_lock:
                self._active += 1
            self._sync_load()
            try:
                self._process(job)
            finally:
                with self._active_lock:
                    self._active -= 1
                self._queue.task_done()
                self._sync_load()

    def _process(self, job: DialogJob) -> None:
        if dialog_store.is_action_finished(job.action):
            logger.info("Действие %s уже завершено, пропускаю", job.action.value)
            return
        instance: InstanceContext | None = None
        if job.context is not None:
            try:
                # Только чтение: шаблоны не создают узлы и связей в БЗ.
                instance = read_context(job.context)
            except Exception as exc:  # noqa: BLE001 - контекст не должен ронять ответ
                logger.warning("Не удалось прочитать контекст rrel_3: %s", exc)
        try:
            # При корректной остановке сервиса `_stop` мягко прерывает генерацию.
            if instance is None:
                result = self._service.answer(job.question, cancel_event=self._stop)
            else:
                result = self._service.answer(
                    job.question, cancel_event=self._stop, context=instance
                )
        except Cancelled:
            dialog_store.complete_assistant_message(
                job.message,
                "Генерация отменена",
                state=kn.STATUS_CANCELLED,
                code="cancelled",
            )
            finish_action_with_status(job.action, True)
            return
        except (LLMUnavailable, LLMTimeout) as exc:
            code = "llm_unavailable" if isinstance(exc, LLMUnavailable) else "llm_timeout"
            logger.warning("Ошибка LLM: %s", exc)
            dialog_store.complete_assistant_message(
                job.message,
                ERROR_MESSAGES[type(exc)],
                state=kn.STATUS_ERROR,
                code=code,
            )
            finish_action_with_status(job.action, False)
            return
        except Exception as exc:  # noqa: BLE001 - причина сохраняется в диалоге
            logger.exception("Ошибка обработки вопроса")
            dialog_store.complete_assistant_message(
                job.message,
                f"Ошибка обработки запроса: {exc}",
                state=kn.STATUS_ERROR,
                code="internal",
            )
            finish_action_with_status(job.action, False)
            return

        source_addrs = [addr for addr in self._source_addrs(result.sources) if addr.is_valid()]
        if instance is not None:
            seen = {addr.value for addr in source_addrs}
            for addr in instance.source_addrs:
                if addr.is_valid() and addr.value not in seen:
                    seen.add(addr.value)
                    source_addrs.append(addr)
        dialog_store.complete_assistant_message(
            job.message,
            result.text,
            model=result.model,
            prompt_version=f"{result.prompt_version}|pack:{result.pack_version}",
            sources=source_addrs,
            state=kn.STATUS_DONE,
            knowledge_source=result.knowledge_source,
            code=DEFAULT_CODE,
        )
        finish_action_with_status(job.action, True)
        logger.info(
            "Ответ сформирован: %s символов, %s оснований, %.0f мс",
            len(result.text),
            len(source_addrs),
            result.latency_ms,
        )

    def _abort_job(self, job: DialogJob, reason: str, code: str) -> None:
        try:
            dialog_store.complete_assistant_message(
                job.message,
                reason,
                state=kn.STATUS_ERROR,
                code=code,
            )
            finish_action_with_status(job.action, False)
        except Exception:  # noqa: BLE001 - остановка не должна падать из-за БЗ
            logger.exception("Не удалось закрыть запрос при остановке")

    @staticmethod
    def _source_addrs(sources: list[dict[str, str]]) -> list[ScAddr]:
        result: list[ScAddr] = []
        for source in sources:
            idtf = source.get("idtf", "")
            if not idtf:
                continue
            addr = ScKeynodes.get(idtf)
            if not addr.is_valid() and idtf in PROPERTY_KEYS:
                addr = ScKeynodes.get(f"concept_ui_{idtf}")
            if addr.is_valid():
                result.append(addr)
        return result

    def _sync_load(self) -> None:
        if self._state is not None:
            self._state.update_load(self._queue.qsize(), self._active)
