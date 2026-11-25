"""T7: rrel_3 доходит от события до воркера и direct-http до промпта."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sc_kpm import ScResult

from ostis_ui_assistant.agents import dialog_agent, worker as worker_module
from ostis_ui_assistant.agents.worker import DialogJob, DialogWorker
from ostis_ui_assistant.api import app as app_module
from ostis_ui_assistant.knowledge.instance import ComponentData, InstanceContext
from ostis_ui_assistant.knowledge.service import AnswerResult
from ostis_ui_assistant.sc import dialog_store


def _answer(text: str = "ответ") -> AnswerResult:
    return AnswerResult(
        text=text,
        model="model",
        prompt_version="v4",
        pack_version="pack",
    )


def test_agent_passes_rrel3_to_job_and_user_message(monkeypatch) -> None:
    question = MagicMock(value=102)
    dialog = MagicMock(value=103)
    context = MagicMock(value=105)
    context.is_valid.return_value = True
    action = MagicMock(value=101)
    result = MagicMock()
    result.is_valid.return_value = False
    monkeypatch.setattr(dialog_agent, "get_action_result", lambda _: result)
    monkeypatch.setattr(
        dialog_agent, "get_action_arguments", lambda *args: [question, dialog, context]
    )
    monkeypatch.setattr(dialog_agent, "get_link_content_data", lambda _: "вопрос")
    monkeypatch.setattr(dialog_agent, "generate_action_result", MagicMock())
    monkeypatch.setattr(dialog_agent, "finish_action_with_status", MagicMock())
    monkeypatch.setattr(dialog_agent.dialog_store, "ensure_dialog", lambda _: dialog)
    monkeypatch.setattr(
        dialog_agent.dialog_store, "append_user_message", MagicMock(return_value=MagicMock())
    )
    monkeypatch.setattr(
        dialog_agent.dialog_store,
        "append_assistant_message",
        MagicMock(return_value=MagicMock()),
    )
    monkeypatch.setattr(dialog_agent, "generate_connector", MagicMock())

    jobs: list[DialogJob] = []

    class FakeWorker:
        queue_size = 0

        def submit(self, job: DialogJob) -> bool:
            jobs.append(job)
            return True

    agent = object.__new__(dialog_agent.UiDialogAgent)
    agent._service = SimpleNamespace(
        settings=SimpleNamespace(llm_model="model"), prompt_version="v4"
    )
    agent._worker = FakeWorker()
    agent._lock = threading.Lock()

    assert agent.on_event(MagicMock(), MagicMock(), action) == ScResult.OK
    dialog_agent.dialog_store.append_user_message.assert_called_once_with(
        dialog, "вопрос", context=context
    )
    assert len(jobs) == 1
    assert jobs[0].context is context


def test_user_message_links_context(monkeypatch) -> None:
    dialog = MagicMock(value=1)
    message = MagicMock(value=2)
    context = MagicMock(value=3)
    relate = MagicMock()
    monkeypatch.setattr(dialog_store, "_append_message", lambda *args, **kwargs: message)
    monkeypatch.setattr(dialog_store, "generate_binary_relation", relate)
    monkeypatch.setattr(
        dialog_store, "ScKeynodes", {"nrel_ui_dialog_context": "relation-addr"}
    )

    assert dialog_store.append_user_message(dialog, "вопрос", context=context) is message
    relate.assert_called_once()
    assert relate.call_args.args[1:4] == (message, context, "relation-addr")


def test_worker_reads_context_before_answer(monkeypatch) -> None:
    instance = InstanceContext(
        mode="selection",
        interface_id="ex_login",
        components=[ComponentData(idtf="ex_login_cmp_10")],
    )
    seen: list[InstanceContext | None] = []
    monkeypatch.setattr(worker_module, "read_context", lambda _: instance)

    class FakeService:
        def answer(self, question, cancel_event=None, context=None):
            seen.append(context)
            return _answer()

    worker = DialogWorker(
        FakeService(), settings=SimpleNamespace(dialog_worker_threads=1, dialog_queue_size=2)
    )
    job = DialogJob(
        action=MagicMock(value=1),
        dialog=MagicMock(value=2),
        question="что делает кнопка?",
        message=MagicMock(value=3),
        context=MagicMock(value=4),
    )
    monkeypatch.setattr(worker_module.dialog_store, "is_action_finished", lambda _: False)
    complete = MagicMock()
    monkeypatch.setattr(worker_module.dialog_store, "complete_assistant_message", complete)
    monkeypatch.setattr(worker_module, "finish_action_with_status", MagicMock())

    worker._process(job)

    assert seen == [instance]
    assert complete.call_args.kwargs["state"] == worker_module.kn.STATUS_DONE


def test_direct_http_ask_with_context_reads_instance(settings, monkeypatch) -> None:
    service_settings = settings
    instance = InstanceContext(
        mode="whole",
        interface_id="ex_login",
        components=[ComponentData(idtf="ex_login_cmp_10")],
    )
    seen: list[InstanceContext | None] = []
    monkeypatch.setattr(app_module, "read_interface", lambda interface_id, ids: instance)

    class FakeService:
        settings = service_settings
        prompt_version = "v4"

        def answer(self, question, cancel_event=None, context=None):
            seen.append(context)
            return _answer()

        def close(self) -> None:
            return None

    app = app_module.create_app(settings, service=FakeService())
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/ask",
            json={
                "question": "какие компоненты?",
                "context": {
                    "mode": "whole",
                    "interface_id": "ex_login",
                    "component_ids": ["ex_login_cmp_10"],
                },
            },
        ) as response:
            assert response.status_code == 200
            response.read()
    assert seen == [instance]


def test_direct_http_rejects_context_without_interface(settings) -> None:
    app = app_module.create_app(settings, service=MagicMock())
    with TestClient(app) as client:
        response = client.post(
            "/ask", json={"question": "вопрос", "context": {"mode": "whole"}}
        )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_request"
