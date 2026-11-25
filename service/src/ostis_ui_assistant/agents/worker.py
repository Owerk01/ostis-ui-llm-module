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
from ..knowledge.history import message_key, prepare_history
from ..knowledge.identifiers import PROPERTY_KEYS
from ..knowledge.instance import InstanceContext, read_context
from ..knowledge.service import Cancelled, KnowledgeService
from ..llm.base import LLMTimeout, LLMUnavailable
from ..sc import dialog_store
from ..sc import keynodes as kn
from ..sc.outcomes import DEFAULT_CODE
from ..sc.service_state import prompt_version_with_contract

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
    # Узел текущего вопроса, чтобы не включить его же в историю промпта.
    question_addr: Any = None


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
        context_addr = job.context
        if context_addr is None:
            # Пользователь может уточнить предыдущий вопрос, не повторно
            # выделяя компонент. Контекст хранится на прошлом сообщении БЗ.
            try:
                context_addr = dialog_store.read_last_context(job.dialog)
            except Exception as exc:  # noqa: BLE001 - контекст не должен ронять ответ
                logger.warning("Не удалось восстановить контекст из истории: %s", exc)
        if context_addr is not None:
            try:
                # Только чтение: шаблоны не создают узлы и связей в БЗ.
                instance = read_context(context_addr)
            except Exception as exc:  # noqa: BLE001 - контекст не должен ронять ответ
                logger.warning("Не удалось прочитать контекст rrel_3: %s", exc)
        history = self._history(job)
        try:
            # При корректной остановке сервиса `_stop` мягко прерывает генерацию.
            answer_kwargs: dict[str, Any] = {"cancel_event": self._stop, "history": history}
            if instance is not None:
                answer_kwargs["context"] = instance
            result = self._service.answer(job.question, **answer_kwargs)
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

        # Основания экземпляра приходят из _sources_for(service) — так же, как
        # основания каталога: по id, реально упомянутым в финальном ответе.
        source_addrs = [
            addr for addr in self._source_addrs(result.sources, instance) if addr.is_valid()
        ]
        dialog_store.complete_assistant_message(
            job.message,
            result.text,
            model=result.model,
            prompt_version=prompt_version_with_contract(
                result.prompt_version, result.pack_version
            ),
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

    def _history(self, job: DialogJob) -> list[dict[str, str]]:
        """Последние завершённые сообщения диалога без текущего вопроса и pending."""
        try:
            raw = dialog_store.read_history(job.dialog)
        except Exception as exc:  # noqa: BLE001 - история не должна ронять ответ
            logger.warning("Не удалось прочитать историю диалога: %s", exc)
            return []
        excluded = {str(job.message.value)}
        question_addr = getattr(job, "question_addr", None)
        if question_addr is not None:
            excluded.add(str(question_addr.value))
        else:
            # Битое состояние: след текущего вопроса мог остаться в истории без
            # адреса в задании. Исключаем последнее совпадение по тексту.
            for item in reversed(raw):
                if item.get("role") == "user" and item.get("text") == job.question:
                    excluded.add(message_key(item))
                    break
        return prepare_history(
            raw,
            getattr(self._settings, "dialog_history_turns", 6),
            exclude_ids=excluded,
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
    def _source_addrs(
        sources: list[dict[str, str]], instance: InstanceContext | None = None
    ) -> list[ScAddr]:
        result: list[ScAddr] = []
        instance_nodes = instance.source_idtfs if instance else {}
        for source in sources:
            idtf = source.get("idtf", "")
            if not idtf:
                continue
            # Узлы экземпляра могут иметь только nrel_ui_id без системного idtf,
            # поэтому адрес берём из прочитанного контекста, а не через resolve.
            addr = instance_nodes.get(idtf)
            if addr is None or not addr.is_valid():
                addr = ScKeynodes.get(idtf)
            if not addr.is_valid() and idtf in PROPERTY_KEYS:
                addr = ScKeynodes.get(f"concept_ui_{idtf}")
            if addr.is_valid():
                result.append(addr)
        return result

    def _sync_load(self) -> None:
        if self._state is not None:
            self._state.update_load(self._queue.qsize(), self._active)
