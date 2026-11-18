"""sc-агент ответа на вопрос разработчика."""

from __future__ import annotations

import logging

from sc_client.models import ScAddr
from sc_kpm import ScAgentClassic, ScKeynodes, ScResult
from sc_kpm.utils import generate_link, get_link_content_data
from sc_kpm.utils.action_utils import (
    finish_action_with_status,
    generate_action_result,
    get_action_arguments,
    get_action_result,
)

from ..knowledge.identifiers import PROPERTY_KEYS
from ..knowledge.service import Cancelled, KnowledgeService
from ..llm.base import LLMTimeout, LLMUnavailable
from ..sc import dialog_store

logger = logging.getLogger(__name__)

ACTION_CLASS = "action_answer_ui_development_question"

ERROR_MESSAGES = {
    LLMUnavailable: "Языковая модель недоступна. Проверьте, что Ollama запущена",
    LLMTimeout: "Превышено время ожидания ответа",
}


class UiDialogAgent(ScAgentClassic):
    def __init__(self, service: KnowledgeService) -> None:
        super().__init__(ACTION_CLASS)
        self._service = service

    def on_event(self, cls: ScAddr, arc: ScAddr, action: ScAddr) -> ScResult:
        if get_action_result(action).is_valid():
            logger.info("Результат уже есть, пропускаю повторную доставку %s", action.value)
            return ScResult.SKIP

        args = get_action_arguments(action, 2)
        question_link = args[0] if args else None
        question = ""
        if question_link is not None and question_link.is_valid():
            question = str(get_link_content_data(question_link)).strip()

        dialog_arg = args[1] if len(args) > 1 else None
        dialog = dialog_store.ensure_dialog(dialog_arg if dialog_arg and dialog_arg.is_valid() else None)
        dialog_store.append_user_message(dialog, question)

        if not question:
            dialog_store.append_error_message(dialog, "Пустой запрос")
            finish_action_with_status(action, False)
            return ScResult.ERROR_INVALID_PARAMS

        try:
            result = self._service.answer(question)
        except Cancelled:
            message = dialog_store.append_assistant_message(
                dialog, "Генерация отменена", self._service.settings.llm_model, "", state="cancelled"
            )
            generate_action_result(action, message)
            finish_action_with_status(action, True)
            return ScResult.OK
        except (LLMUnavailable, LLMTimeout) as exc:
            reason = ERROR_MESSAGES[type(exc)]
            logger.warning("Ошибка LLM: %s", exc)
            message = dialog_store.append_error_message(dialog, reason)
            generate_action_result(action, message)
            finish_action_with_status(action, False)
            return ScResult.ERROR
        except Exception as exc:  # noqa: BLE001 - причина сохраняется в диалоге
            logger.exception("Ошибка обработки вопроса")
            message = dialog_store.append_error_message(dialog, f"Ошибка обработки запроса: {exc}")
            generate_action_result(action, message)
            finish_action_with_status(action, False)
            return ScResult.ERROR

        source_addrs = self._source_addrs(result.sources)
        source_addrs = [addr for addr in source_addrs if addr.is_valid()]
        message = dialog_store.append_assistant_message(
            dialog,
            result.text,
            result.model,
            f"{result.prompt_version}|pack:{result.pack_version}",
            source_addrs,
        )
        generate_action_result(
            action, generate_link(result.text), message, *source_addrs
        )
        finish_action_with_status(action, True)
        logger.info(
            "Ответ сформирован: %s символов, %s оснований, %.0f мс",
            len(result.text),
            len(source_addrs),
            result.latency_ms,
        )
        return ScResult.OK

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
