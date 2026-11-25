"""sc-агент ответа на вопрос разработчика.

`on_event` не генерирует ответ: он валидирует аргументы, создаёт pending-
сообщение и кладёт запрос в ограниченную очередь. Тяжёлая работа — в
`DialogWorker` (B0-1).
"""

from __future__ import annotations

import logging
import threading

from sc_client.constants import sc_type
from sc_client.models import ScAddr
from sc_kpm import ScAgentClassic, ScResult
from sc_kpm.utils import generate_connector, get_link_content_data
from sc_kpm.utils.action_utils import (
    finish_action_with_status,
    generate_action_result,
    get_action_arguments,
    get_action_result,
)

from ..sc import dialog_store
from ..sc import keynodes as kn
from ..sc.outcomes import PENDING_CODE
from .worker import BUSY_MESSAGE, DialogJob, DialogWorker

logger = logging.getLogger(__name__)

ACTION_CLASS = "action_answer_ui_development_question"


class UiDialogAgent(ScAgentClassic):
    def __init__(self, service, worker: DialogWorker) -> None:
        super().__init__(ACTION_CLASS)
        self._service = service
        self._worker = worker
        # События одного действия могут прийти одновременно: без блокировки
        # два обработчика увидят пустой результат и создадут два сообщения.
        self._lock = threading.Lock()

    @staticmethod
    def _attach_message(action: ScAddr, result: ScAddr, message: ScAddr) -> None:
        """Кладёт сообщение в существующий результат или создаёт результат."""
        if result.is_valid():
            generate_connector(sc_type.CONST_PERM_POS_ARC, result, message)
        else:
            generate_action_result(action, message)

    def on_event(self, cls: ScAddr, arc: ScAddr, action: ScAddr) -> ScResult:
        with self._lock:
            result = get_action_result(action)
            message = (
                dialog_store.find_assistant_message_in_result(result)
                if result.is_valid()
                else None
            )
            # B0-2: идемпотентность проверяет и результат, и assistant-сообщение.
            # Одного результата мало: без сообщения панель нечего показать.
            if message is not None:
                logger.info(
                    "Действие %s уже обработано (сообщение %s), пропускаю",
                    action.value,
                    message.value,
                )
                return ScResult.SKIP
            if result.is_valid():
                logger.warning(
                    "У действия %s есть результат, но нет assistant-сообщения; "
                    "дополняю результат",
                    action.value,
                )

            args = get_action_arguments(action, 2)
            question_link = args[0] if args else None
            question = ""
            if question_link is not None and question_link.is_valid():
                question = str(get_link_content_data(question_link)).strip()

            dialog_arg = args[1] if len(args) > 1 else None
            dialog = dialog_store.ensure_dialog(
                dialog_arg if dialog_arg and dialog_arg.is_valid() else None
            )

            if not question:
                message = dialog_store.append_error_message(
                    dialog, "Пустой запрос", code="invalid_request"
                )
                self._attach_message(action, result, message)
                finish_action_with_status(action, False)
                return ScResult.ERROR_INVALID_PARAMS

            # Если результат уже есть (битое состояние), пользовательское
            # сообщение могло быть записано раньше — не дублируем его.
            if not result.is_valid():
                dialog_store.append_user_message(dialog, question)
            message = dialog_store.append_assistant_message(
                dialog,
                "",
                self._service.settings.llm_model,
                self._service.prompt_version,
                state=kn.STATUS_PENDING,
                knowledge_source="unknown",
                code=PENDING_CODE,
            )
            # Результат фиксируется сразу: повторная доставка события увидит
            # сообщение и вернёт SKIP, не создавая второй ответ (B0-2).
            self._attach_message(action, result, message)

            job = DialogJob(
                action=action,
                dialog=dialog,
                question=question,
                message=message,
            )
            if not self._worker.submit(job):
                logger.warning("Очередь запросов переполнена, действие %s: busy", action.value)
                dialog_store.complete_assistant_message(
                    message,
                    BUSY_MESSAGE,
                    state=kn.STATUS_ERROR,
                    code="busy",
                )
                finish_action_with_status(action, False)
                return ScResult.OK

            logger.info(
                "Запрос %s принят в очередь (размер %s)",
                action.value,
                self._worker.queue_size,
            )
            return ScResult.OK
