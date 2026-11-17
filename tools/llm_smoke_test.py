#!/usr/bin/env python3
"""Смоук локальной LLM без системного промпта (M0-T4).

Задаёт три русскоязычных вопроса о каталоге ПИ и печатает связность ответа
(непустой текст) и скорость генерации. Ничего не пишет в БЗ и не использует
knowledge pack — это проверка самой модели до M1.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request

BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "qwen3.5:4b")

QUESTIONS = [
    "Перечисли основные типы компонентов пользовательского интерфейса в OSTIS "
    "и кратко опиши их назначение. Ответь на русском.",
    "Чем отличается кнопка (button) от пункта меню (menu_item) в модели "
    "пользовательского интерфейса? Ответь на русском.",
    "Какие свойства есть у компонента пользовательского интерфейса и что задаёт "
    "свойство visible? Ответь на русском.",
]


def ask(question: str) -> dict:
    payload = {
        "model": MODEL,
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {"num_ctx": 8192, "temperature": 0.2, "top_p": 0.9},
        "messages": [{"role": "user", "content": question}],
    }
    request = urllib.request.Request(
        f"{BASE_URL}/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=300) as response:
        data = json.loads(response.read().decode("utf-8"))
    elapsed = time.perf_counter() - started

    content = (data.get("message") or {}).get("content", "").strip()
    output_tokens = int(data.get("eval_count") or 0)
    return {
        "answer": content,
        "elapsed_s": elapsed,
        "prompt_tokens": data.get("prompt_eval_count"),
        "output_tokens": output_tokens,
        "tokens_per_s": round(output_tokens / elapsed, 2) if elapsed > 0 else None,
    }


def main() -> int:
    print(f"LLM: {BASE_URL} / {MODEL}")
    for index, question in enumerate(QUESTIONS, start=1):
        result = ask(question)
        print(f"\n--- Вопрос {index} ---")
        print(question)
        print(f"Ответ ({len(result['answer'])} символов):")
        print(result["answer"] if result["answer"] else "<ПУСТО>")
        print(
            f"latency={result['elapsed_s']:.2f}s "
            f"prompt_tokens={result['prompt_tokens']} "
            f"output_tokens={result['output_tokens']} "
            f"tok/s={result['tokens_per_s']}"
        )
        if not result["answer"]:
            print("ОШИБКА: пустой ответ модели", flush=True)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
