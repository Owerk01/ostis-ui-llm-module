"""Контрактные тесты конфигурации сервиса."""

from __future__ import annotations

import pytest

from ostis_ui_assistant.config import Settings


def test_timeout_order_validation() -> None:
    """Падение при старте, если клиентский таймаут не строго больше LLM."""
    # client > llm — ок
    Settings(llm_timeout_s=25.0, dialog_client_timeout_s=35.0)
    # client == llm — ошибка
    with pytest.raises(Exception):
        Settings(llm_timeout_s=25.0, dialog_client_timeout_s=25.0)
    # client < llm — ошибка
    with pytest.raises(Exception):
        Settings(llm_timeout_s=25.0, dialog_client_timeout_s=20.0)
    # дефолтные значения удовлетворяют правилу
    s = Settings()
    assert s.dialog_client_timeout_s > s.llm_timeout_s


def test_defaults_satisfy_timeout_order() -> None:
    s = Settings()
    assert s.llm_timeout_s == 25.0
    assert s.dialog_client_timeout_s == 35.0
    assert s.dialog_client_timeout_s > s.llm_timeout_s
