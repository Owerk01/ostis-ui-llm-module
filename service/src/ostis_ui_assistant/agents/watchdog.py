"""Закрытие «висячих» действий после аварийного завершения агента (B0-1)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sc_client.constants import sc_type
from sc_client.models import ScTemplate
from sc_client.client import search_by_template
from sc_kpm import ScKeynodes
from sc_kpm.utils import generate_connector
from sc_kpm.utils.action_utils import (
    finish_action_with_status,
    generate_action_result,
    get_action_arguments,
    get_action_result,
)

from ..config import Settings
from ..sc import dialog_store

logger = logging.getLogger(__name__)

ACTION_CLASS = "action_answer_ui_development_question"
ORPHAN_MESSAGE = (
    "Обработка прервана: агент диалога был перезапущен. "
    "Повторите вопрос, если ответ нужен."
)


def _age_minutes(value: str | None) -> float | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - moment).total_seconds() / 60


def _orphan_actions():
    templ = ScTemplate()
    templ.triple(
        ScKeynodes[ACTION_CLASS],
        sc_type.VAR_PERM_POS_ARC,
        sc_type.VAR_NODE >> "_action",
    )
    for row in search_by_template(templ):
        action = row.get("_action")
        if not action.is_valid():
            continue
        if dialog_store.is_action_finished(action):
            continue
        if not dialog_store.is_action_initiated(action):
            continue
        yield action


def close_orphan_actions(settings: Settings) -> int:
    """Завершает initiated-действия нашего класса без action_finished.

    Возраст не мешает закрыть действие (иначе мусор останется навсегда), но
    используется в логе: старые запросы не «подхватываются» для генерации.
    """
    closed = 0
    for action in _orphan_actions():
        age: float | None = None
        try:
            message = dialog_store.find_assistant_message(action)
            if message is not None:
                age = _age_minutes(dialog_store.message_time(message))
                dialog_store.complete_assistant_message(
                    message,
                    ORPHAN_MESSAGE,
                    state="error",
                    code="agent_restarted",
                )
            else:
                args = get_action_arguments(action, 2)
                dialog = args[1] if len(args) > 1 else None
                if dialog is not None and dialog.is_valid():
                    message = dialog_store.append_error_message(
                        dialog, ORPHAN_MESSAGE, code="agent_restarted"
                    )
                    result = get_action_result(action)
                    if result.is_valid():
                        generate_connector(
                            sc_type.CONST_PERM_POS_ARC, result, message
                        )
                    else:
                        generate_action_result(action, message)
                else:
                    logger.warning(
                        "У висячего действия %s нет диалога (rrel_2)", action.value
                    )
        except Exception:  # noqa: BLE001 - одно битое действие не блокирует старт
            logger.exception("Не удалось оформить висячее действие %s", action.value)
        finally:
            # Главное требование watchdog: в БЗ не остаётся initiated-действий
            # без статуса, даже если сообщение оформить не удалось.
            try:
                finish_action_with_status(action, False)
                closed += 1
            except Exception:  # noqa: BLE001 - старт важнее одного действия
                logger.exception(
                    "Не удалось завершить висячее действие %s", action.value
                )
        if age is not None and age > settings.watchdog_max_age_minutes:
            logger.warning(
                "Закрыто старое действие %s (возраст %.0f мин, порог %s мин)",
                action.value,
                age,
                settings.watchdog_max_age_minutes,
            )
        else:
            logger.info("Закрыто висячее действие %s как agent_restarted", action.value)
    if closed:
        logger.warning("Watchdog закрыл висячих действий: %s", closed)
    return closed
