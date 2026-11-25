"""Точка входа сервиса: режим выбирается ASSISTANT_TRANSPORT."""

from __future__ import annotations

import logging

import uvicorn

from .api.app import create_app
from .config import Settings


def run_sc_memory(settings: Settings) -> None:
    """Боевой режим: sc-агент внутри sc-machine, обмен только через БЗ."""
    from sc_kpm import ScServer

    from .agents.module import UiDialogModule
    from .agents.watchdog import close_orphan_actions
    from .agents.worker import DialogWorker
    from .knowledge.service import KnowledgeService
    from .sc.keynodes import init_keynodes
    from .sc.service_state import ServiceState

    logger = logging.getLogger(__name__)
    server = ScServer(settings.sc_ws_url)
    with server.connect():
        init_keynodes()
        state = ServiceState(settings)
        if not state.acquire():
            # Второй экземпляр не должен регистрировать обработчик вообще.
            raise SystemExit(1)

        state.start_heartbeat()
        service = None
        worker = None
        try:
            service = KnowledgeService(settings, state=state)
            worker = DialogWorker(service, settings, state)
            closed = close_orphan_actions(settings)
            if closed:
                logger.warning("Watchdog закрыл висячих действий: %s", closed)

            worker.start()
            module = UiDialogModule(service, worker)
            server.add_modules(module)
            state.mark_ready(
                pack_version=service.pack_version,
                knowledge_source=service.knowledge_source,
                kb_partial=service.kb_status.partial,
                kb_missing=service.kb_status.missing,
            )
            with server.register_modules():
                logger.info(
                    "sc-агент %s зарегистрирован, ожидание действий",
                    "action_answer_ui_development_question",
                )
                server.serve()
        finally:
            state.set_state("stopping")
            if worker is not None:
                worker.stop(timeout=5.0)
            if service is not None:
                service.close()
            state.stop_heartbeat()
            state.release()


def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if settings.assistant_transport == "sc-memory":
        run_sc_memory(settings)
        return

    app = create_app(settings)
    # Передаём объект приложения, а не строку импорта: иначе модуль загружается
    # повторно и создаются два KnowledgeService/два LLM-клиента.
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
