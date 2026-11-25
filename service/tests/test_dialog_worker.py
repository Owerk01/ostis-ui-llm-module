"""B0-1: воркер обновляет pending-сообщение и завершает действие."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from ostis_ui_assistant.agents import worker as worker_module
from ostis_ui_assistant.agents.worker import DialogJob, DialogWorker
from ostis_ui_assistant.knowledge.service import AnswerResult
from ostis_ui_assistant.llm.base import LLMTimeout, LLMUnavailable
from ostis_ui_assistant.sc.outcomes import is_retryable


def _job() -> DialogJob:
    return DialogJob(
        action=MagicMock(value=201),
        dialog=MagicMock(value=202),
        question="вопрос",
        message=MagicMock(value=203),
    )


def _settings() -> SimpleNamespace:
    return SimpleNamespace(dialog_worker_threads=1, dialog_queue_size=2)


def _patch_common(monkeypatch, *, finished: bool = False):
    monkeypatch.setattr(
        worker_module.dialog_store, "is_action_finished", lambda _: finished
    )
    complete = MagicMock()
    monkeypatch.setattr(
        worker_module.dialog_store, "complete_assistant_message", complete
    )
    finish = MagicMock()
    monkeypatch.setattr(worker_module, "finish_action_with_status", finish)
    return complete, finish


def test_success_writes_answer_to_same_message(monkeypatch) -> None:
    complete, finish = _patch_common(monkeypatch)
    service = MagicMock()
    service.answer.return_value = AnswerResult(
        text="ответ",
        model="qwen",
        prompt_version="v4",
        pack_version="2026-11-18T18:02:18Z",
        sources=[],
        latency_ms=1.0,
        knowledge_source="kb",
    )
    job = _job()

    DialogWorker(service, _settings())._process(job)

    kwargs = complete.call_args.kwargs
    assert complete.call_args.args[0] is job.message
    assert complete.call_args.args[1] == "ответ"
    assert kwargs["state"] == "done"
    assert kwargs["code"] == "ok"
    assert kwargs["knowledge_source"] == "kb"
    finish.assert_called_once_with(job.action, True)


def test_llm_unavailable_is_retryable(monkeypatch) -> None:
    complete, finish = _patch_common(monkeypatch)
    service = MagicMock()
    service.answer.side_effect = LLMUnavailable("нет соединения")
    job = _job()

    DialogWorker(service, _settings())._process(job)

    code = complete.call_args.kwargs["code"]
    assert code == "llm_unavailable"
    assert is_retryable(code) is True
    finish.assert_called_once_with(job.action, False)


def test_timeout_marks_message_error_and_action_unsuccessful(monkeypatch) -> None:
    complete, finish = _patch_common(monkeypatch)
    service = MagicMock()
    service.answer.side_effect = LLMTimeout("too long")
    job = _job()

    DialogWorker(service, _settings())._process(job)

    assert complete.call_args.kwargs["state"] == "error"
    assert complete.call_args.kwargs["code"] == "llm_timeout"
    finish.assert_called_once_with(job.action, False)


def test_finished_action_is_skipped(monkeypatch) -> None:
    complete, finish = _patch_common(monkeypatch, finished=True)
    service = MagicMock()

    DialogWorker(service, _settings())._process(_job())

    service.answer.assert_not_called()
    complete.assert_not_called()
    finish.assert_not_called()


def test_stop_closes_queued_jobs(monkeypatch) -> None:
    complete, finish = _patch_common(monkeypatch)
    worker = DialogWorker(MagicMock(), _settings())
    job = _job()
    assert worker.submit(job) is True

    worker.stop()

    assert complete.call_args.kwargs["code"] == "agent_restarted"
    finish.assert_called_once_with(job.action, False)
