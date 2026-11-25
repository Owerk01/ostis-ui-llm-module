"""B0-1/B0-2: обработчик события не ждёт LLM, дубли и busy обрабатываются."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

from sc_kpm import ScResult

from ostis_ui_assistant.agents import dialog_agent


class SlowService:
    """Заглушка LLM: если on_event её вызовет, тест это заметит."""

    settings = SimpleNamespace(llm_model="qwen3.5:4b")
    prompt_version = "v4"

    def __init__(self) -> None:
        self.called = False

    def answer(self, question: str):
        self.called = True
        time.sleep(10)
        raise AssertionError("on_event не должен вызывать генерацию")


class FakeWorker:
    def __init__(self, *, accept: bool = True) -> None:
        self.accept = accept
        self.jobs = []
        self.queue_size = 0

    def submit(self, job) -> bool:
        self.jobs.append(job)
        return self.accept


def make_agent(service, worker):
    agent = object.__new__(dialog_agent.UiDialogAgent)
    agent._service = service
    agent._worker = worker
    agent._lock = threading.Lock()
    return agent


def patch_sc(
    monkeypatch, *, result_valid: bool = False, message_in_result: bool = True
):
    action = MagicMock(value=101)
    question = MagicMock(value=102)
    dialog = MagicMock(value=103)
    message = MagicMock(value=104)
    result = MagicMock()
    result.is_valid.return_value = result_valid

    monkeypatch.setattr(dialog_agent, "get_action_result", lambda _: result)
    monkeypatch.setattr(
        dialog_agent, "get_action_arguments", lambda *_: [question, dialog]
    )
    monkeypatch.setattr(dialog_agent, "get_link_content_data", lambda _: "вопрос")
    monkeypatch.setattr(
        dialog_agent, "generate_action_result", MagicMock(return_value=None)
    )
    monkeypatch.setattr(
        dialog_agent, "finish_action_with_status", MagicMock(return_value=None)
    )
    monkeypatch.setattr(dialog_agent.dialog_store, "ensure_dialog", lambda _: dialog)
    monkeypatch.setattr(
        dialog_agent.dialog_store, "append_user_message", MagicMock(return_value=MagicMock())
    )
    monkeypatch.setattr(
        dialog_agent.dialog_store,
        "append_assistant_message",
        MagicMock(return_value=message),
    )
    monkeypatch.setattr(
        dialog_agent.dialog_store,
        "complete_assistant_message",
        MagicMock(return_value=None),
    )
    monkeypatch.setattr(
        dialog_agent.dialog_store,
        "find_assistant_message_in_result",
        MagicMock(return_value=MagicMock(value=104) if message_in_result else None),
    )
    monkeypatch.setattr(
        dialog_agent, "generate_connector", MagicMock(return_value=None)
    )
    return action


def test_event_handler_returns_fast(monkeypatch) -> None:
    service = SlowService()
    worker = FakeWorker()
    action = patch_sc(monkeypatch)
    agent = make_agent(service, worker)

    started = time.perf_counter()
    result = agent.on_event(MagicMock(), MagicMock(), action)
    elapsed = time.perf_counter() - started

    assert result == ScResult.OK
    assert elapsed < 0.1, f"on_event занял {elapsed:.3f} с"
    assert service.called is False
    assert len(worker.jobs) == 1
    assert dialog_agent.dialog_store.append_assistant_message.call_args.kwargs["code"] == "pending"


def test_single_turn_per_action(monkeypatch) -> None:
    """Одно действие создаёт ровно одно user- и одно assistant-сообщение."""
    service = SlowService()
    worker = FakeWorker()
    action = patch_sc(monkeypatch)
    agent = make_agent(service, worker)

    agent.on_event(MagicMock(), MagicMock(), action)

    assert dialog_agent.dialog_store.append_user_message.call_count == 1
    assert dialog_agent.dialog_store.append_assistant_message.call_count == 1


def test_queue_overflow_finishes_with_busy(monkeypatch) -> None:
    service = SlowService()
    worker = FakeWorker(accept=False)
    action = patch_sc(monkeypatch)
    agent = make_agent(service, worker)

    result = agent.on_event(MagicMock(), MagicMock(), action)

    assert result == ScResult.OK
    assert service.called is False
    kwargs = dialog_agent.dialog_store.complete_assistant_message.call_args.kwargs
    assert kwargs["code"] == "busy"
    dialog_agent.finish_action_with_status.assert_called_once_with(action, False)


def test_duplicate_delivery_skips_without_new_message(monkeypatch) -> None:
    service = SlowService()
    worker = FakeWorker()
    action = patch_sc(monkeypatch, result_valid=True)
    agent = make_agent(service, worker)

    result = agent.on_event(MagicMock(), MagicMock(), action)

    assert result == ScResult.SKIP
    assert service.called is False
    dialog_agent.dialog_store.append_user_message.assert_not_called()
    assert worker.jobs == []


def test_result_without_message_is_completed_not_duplicated(monkeypatch) -> None:
    """Результат без assistant-сообщения — битое состояние: дополняем его."""
    service = SlowService()
    worker = FakeWorker()
    action = patch_sc(monkeypatch, result_valid=True, message_in_result=False)
    agent = make_agent(service, worker)

    result = agent.on_event(MagicMock(), MagicMock(), action)

    assert result == ScResult.OK
    dialog_agent.generate_action_result.assert_not_called()
    dialog_agent.generate_connector.assert_called_once()
    # Пользовательское сообщение уже могло быть записано до результата.
    dialog_agent.dialog_store.append_user_message.assert_not_called()
    assert len(worker.jobs) == 1
