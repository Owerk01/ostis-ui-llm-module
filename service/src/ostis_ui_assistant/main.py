"""Точка входа сервиса: режим выбирается ASSISTANT_TRANSPORT (AGENTS.md 3.4)."""

from __future__ import annotations

import logging

import uvicorn

from .api.app import create_app
from .config import Settings


def run_sc_memory(settings: Settings) -> None:
    """Боевой режим: sc-агент внутри sc-machine, обмен только через БЗ."""
    from sc_kpm import ScServer

    from .agents.module import UiDialogModule
    from .knowledge.service import KnowledgeService
    from .sc.keynodes import init_keynodes

    server = ScServer(settings.sc_ws_url)
    with server.connect():
        init_keynodes()
        service = KnowledgeService(settings)
        module = UiDialogModule(service)
        server.add_modules(module)
        try:
            with server.register_modules():
                logging.getLogger(__name__).info(
                    "sc-агент %s зарегистрирован, ожидание действий",
                    "action_answer_ui_development_question",
                )
                server.serve()
        finally:
            service.close()


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
