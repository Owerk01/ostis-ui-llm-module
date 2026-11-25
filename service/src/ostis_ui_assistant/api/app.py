"""FastAPI direct-http режим: /health, /ask (SSE), /cancel."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..config import Settings
from ..knowledge.service import Cancelled, KnowledgeService
from ..llm.base import LLMTimeout, LLMUnavailable
from ..sc.outcomes import PENDING_CODE
from .sse import (
    CancelRegistry,
    DialogStore,
    sse_event,
    split_for_stream,
)

logger = logging.getLogger(__name__)


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    dialog_id: str | None = None


class CancelRequest(BaseModel):
    message_id: str


class DialogResponse(BaseModel):
    dialog_id: str


class DialogExistsResponse(BaseModel):
    dialog_id: str
    exists: bool


def create_app(
    settings: Settings | None = None,
    service: KnowledgeService | None = None,
) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    knowledge = service or KnowledgeService(settings)
    dialogs = DialogStore()
    cancels = CancelRegistry()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        knowledge.close()

    app = FastAPI(title="ostis-ui-assistant", version="0.1.0", lifespan=lifespan)
    app.state.knowledge = knowledge
    app.state.dialogs = dialogs
    app.state.cancels = cancels

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict:
        return knowledge.health()

    @app.post("/dialog", response_model=DialogResponse)
    def create_dialog() -> DialogResponse:
        return DialogResponse(dialog_id=dialogs.create_dialog())

    @app.get("/dialog/{dialog_id}", response_model=DialogExistsResponse)
    def dialog(dialog_id: str) -> DialogExistsResponse:
        return DialogExistsResponse(dialog_id=dialog_id, exists=dialogs.exists(dialog_id))

    @app.get("/history/{dialog_id}")
    def history(dialog_id: str) -> list[dict]:
        return dialogs.history(dialog_id)

    @app.post("/cancel")
    def cancel(request: CancelRequest) -> dict:
        cancelled = cancels.cancel(request.message_id)
        return {"cancelled": cancelled, "message_id": request.message_id}

    @app.post("/ask")
    def ask(request: AskRequest) -> StreamingResponse:
        question = request.question.strip()
        if not question:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_request", "error": "Пустой запрос"},
            )

        if request.dialog_id:
            dialog_id = request.dialog_id
            if not dialogs.exists(request.dialog_id):
                # Неизвестный диалог не подменяет существующий: клиент передаёт id,
                # которого ещё нет в сервисе — это ошибка, а не новый диалог.
                raise HTTPException(
                    status_code=404,
                    detail={"code": "dialog_not_found", "dialog_id": request.dialog_id},
                )
        else:
            dialog_id = dialogs.create_dialog()
        dialogs.add_user_message(dialog_id, question)
        assistant = dialogs.add_assistant_pending(dialog_id)
        cancel_event = cancels.create(assistant.id)

        def generate() -> Iterator[str]:
            yield sse_event(
                "meta",
                {
                    "message_id": assistant.id,
                    "dialog_id": dialog_id,
                    "state": "pending",
                    "code": PENDING_CODE,
                },
            )
            try:
                result = knowledge.answer(question, cancel_event)
                dialogs.update_assistant(
                    dialog_id,
                    assistant.id,
                    text=result.text,
                    state="done",
                    code="ok",
                    sources=result.sources,
                )
                for chunk in split_for_stream(result.text):
                    yield sse_event("delta", {"text": chunk})
                message = next(
                    (
                        item
                        for item in dialogs.history(dialog_id)
                        if item["id"] == assistant.id
                    ),
                    None,
                )
                yield sse_event(
                    "done",
                    {
                        "message": message,
                        "model": result.model,
                        "prompt_version": result.prompt_version,
                        "pack_version": result.pack_version,
                        "latency_ms": result.latency_ms,
                        "prompt_tokens": result.prompt_tokens,
                        "output_tokens": result.output_tokens,
                    },
                )
            except Cancelled:
                dialogs.update_assistant(
                    dialog_id,
                    assistant.id,
                    text="",
                    state="cancelled",
                    code="cancelled",
                    error=None,
                )
                message = next(
                    (
                        item
                        for item in dialogs.history(dialog_id)
                        if item["id"] == assistant.id
                    ),
                    None,
                )
                yield sse_event("cancelled", {"message": message})
            except LLMUnavailable:
                error_text = "Языковая модель недоступна. Проверьте, что Ollama запущена"
                logger.warning("LLM недоступна при обработке запроса %s", assistant.id)
                dialogs.update_assistant(
                    dialog_id,
                    assistant.id,
                    text="",
                    state="error",
                    code="llm_unavailable",
                    error=error_text,
                )
                yield sse_event(
                    "error",
                    {
                        "message_id": assistant.id,
                        "error": error_text,
                        "state": "error",
                        "code": "llm_unavailable",
                    },
                )
            except LLMTimeout:
                error_text = "Превышено время ожидания ответа"
                logger.warning("Таймаут LLM при обработке запроса %s", assistant.id)
                dialogs.update_assistant(
                    dialog_id,
                    assistant.id,
                    text="",
                    state="error",
                    code="llm_timeout",
                    error=error_text,
                )
                yield sse_event(
                    "error",
                    {
                        "message_id": assistant.id,
                        "error": error_text,
                        "state": "error",
                        "code": "llm_timeout",
                    },
                )
            except Exception as exc:  # сервис не должен ронять поток
                logger.exception("Ошибка обработки запроса: %s", exc)
                error_text = "Не удалось получить ответ. Подробности в журнале сервиса"
                dialogs.update_assistant(
                    dialog_id,
                    assistant.id,
                    text="",
                    state="error",
                    code="internal",
                    error=error_text,
                )
                yield sse_event(
                    "error",
                    {
                        "message_id": assistant.id,
                        "error": error_text,
                        "state": "error",
                        "code": "internal",
                    },
                )
            finally:
                cancels.remove(assistant.id)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app
