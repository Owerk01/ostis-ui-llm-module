"""E2E-проверка панели через headless Chrome.

Запускается вручную при поднятых сервисе и dev-сервере панели:
    pip install playwright
    .venv/bin/python tools/e2e_panel.py
Требует playwright и системный Chrome (скачивание браузеров не нужно).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PANEL_URL = "http://localhost:5173/"
CHROME = "/usr/bin/google-chrome-stable"
MODE = os.environ.get("E2E_MODE", "direct-http")
SCREENSHOT = Path(
    "docs/screenshots/m2-panel-sc.png" if MODE == "sc-memory" else "docs/screenshots/m1-panel.png"
)


def main() -> int:
    SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--no-sandbox"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.add_init_script(
            "window.localStorage.setItem('oaa.dev.kind', '" + MODE + "')"
        )
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))

        page.goto(PANEL_URL, wait_until="networkidle")
        page.get_by_role("heading", name="Ассистент разработчика ПИ").wait_for()
        if MODE == "sc-memory":
            page.get_by_text("Знания из БЗ").wait_for(timeout=15_000)
            print("health: режим sc-memory, знания из БЗ")
        else:
            page.get_by_text("Знания из локальной копии").wait_for()
            print("health: статус fallback отображается")

        # --- Вопрос о свойстве: индикация, стрим, основания -------------------
        page.locator("#oaa-question").fill("Что задаёт свойство action_id?")
        started = page.evaluate("performance.now()")
        page.get_by_role("button", name="Отправить").click()
        page.wait_for_function("document.body.innerText.includes('Обработка запроса')")
        indicator_ms = page.evaluate("performance.now()") - started
        print(f"indicator_ms={indicator_ms:.0f}")
        assert indicator_ms <= 300, f"индикация появилась за {indicator_ms:.0f} мс > 300"

        page.get_by_role("button", name="Отмена").wait_for(state="visible")
        page.wait_for_function(
            "!document.body.innerText.includes('Обработка запроса')",
            timeout=60_000,
        )
        chips = page.locator('button[title*="concept_ui_"]')
        chips.first.wait_for(timeout=10_000)
        assert chips.count() > 0
        chips.first.click()
        page.get_by_text("Выбрано основание").wait_for(timeout=2_000)
        body = page.locator("body").inner_text()
        assert "concept_ui_" in body
        print("answer: ответ про action_id получен, чипы оснований кликабельны")
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        print(f"screenshot: {SCREENSHOT}")

        # --- Негативный вопрос ------------------------------------------------
        page.locator("#oaa-question").fill("Есть ли в каталоге компонент «диаграмма Ганта»?")
        page.get_by_role("button", name="Отправить").click()
        page.wait_for_function(
            "!document.body.innerText.includes('Обработка запроса')",
            timeout=60_000,
        )
        body = page.locator("body").inner_text().lower()
        assert "нет сведений" in body or "отсутств" in body, body[-500:]
        print("negative: отказ вместо выдумки получен")

        # --- Отмена -----------------------------------------------------------
        page.locator("#oaa-question").fill("Какие принципы разработки ПИ есть в базе знаний?")
        page.get_by_role("button", name="Отправить").click()
        cancel_button = page.get_by_role("button", name="Отмена")
        cancel_button.wait_for(state="visible", timeout=2_000)
        cancel_button.click()
        page.get_by_text("Отменено").first.wait_for(timeout=5_000)
        print("cancel: сообщение помечено «Отменено»")

        if console_errors:
            print("console errors:")
            for error in console_errors:
                print("  ", error)
        else:
            print("console: ошибок нет")

        browser.close()

    return 0 if not console_errors else 1


if __name__ == "__main__":
    sys.exit(main())
