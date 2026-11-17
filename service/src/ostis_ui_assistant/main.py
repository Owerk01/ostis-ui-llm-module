"""Точка входа direct-http режима (M1)."""

from __future__ import annotations

import uvicorn

from .api.app import create_app
from .config import Settings

settings = Settings()
app = create_app(settings)


def main() -> None:
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
