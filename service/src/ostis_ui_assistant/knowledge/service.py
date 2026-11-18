"""Сервис ответа: knowledge pack + LLM + пост-валидация (M1-T3…T5)."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import Settings
from ..llm.base import LLMBackend, LLMError, LLMStats, LLMTimeout, create_backend
from .identifiers import ALL_IDENTIFIERS, PROPERTY_KEYS
from .kb_reader import KbStatus, close as close_kb, load_pack_from_kb
from .render import (
    PromptBuildResult,
    build_messages,
    build_prompt,
    load_pack,
    load_template,
)
from .validate import ValidationResult, extract_identifiers, validate_answer

logger = logging.getLogger(__name__)


class Cancelled(Exception):
    """Генерация отменена пользователем."""


@dataclass
class AnswerResult:
    text: str
    model: str
    prompt_version: str
    pack_version: str
    sources: list[dict[str, str]] = field(default_factory=list)
    prompt_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    validation_removed: list[str] = field(default_factory=list)
    hallucinated: bool = False
    knowledge_source: str = "fallback"


class KnowledgeService:
    def __init__(self, settings: Settings, backend: LLMBackend | None = None) -> None:
        self.settings = settings
        self.pack = load_pack(settings.knowledge_pack_path)
        self.template = load_template(settings.prompt_path)
        self.kb_status = KbStatus()
        if settings.knowledge_source == "kb":
            self.pack, self.kb_status = load_pack_from_kb(
                self.pack,
                settings.sc_ws_url,
                allow_fallback=settings.kb_fallback_allowed,
            )
        self.knowledge_source = self.kb_status.source
        self.backend = backend or create_backend(settings)
        self._log_lock = threading.Lock()
        self._prompt: PromptBuildResult = build_prompt(self.pack, self.template)
        self._source_map = self._build_source_map()

        logger.info(
            "Knowledge pack %s (%s): %s типов, %s свойств, %s отношений; промпт ~%s токенов",
            self.pack.get("pack_version"),
            self.knowledge_source,
            len(self.pack.get("component_types", [])),
            len(self.pack.get("properties", [])),
            len(self.pack.get("relations", [])),
            self._prompt.knowledge_tokens,
        )

    @property
    def pack_version(self) -> str:
        return str(self.pack.get("pack_version", "unknown"))

    @property
    def prompt_version(self) -> str:
        return self.settings.prompt_version

    def _build_source_map(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for item in self.pack.get("component_types", []):
            result[item["sc_class"]] = item.get("label_ru", item["type_id"])
        for item in self.pack.get("properties", []):
            result[item["sc_class"]] = f"свойство {item['key']}"
        for item in self.pack.get("relations", []):
            result[item["idtf"]] = item.get("meaning_ru", "отношение")
        return result

    def _sources_for(self, text: str) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        seen: set[str] = set()
        for identifier in extract_identifiers(text):
            if identifier in seen or identifier not in self._source_map:
                continue
            seen.add(identifier)
            sources.append({"idtf": identifier, "labelRu": self._source_map[identifier]})
        return sources

    def _repair(self, text: str, unknown: list[str]) -> str:
        allowed = ", ".join(sorted(ALL_IDENTIFIERS | PROPERTY_KEYS))
        request = (
            "В ответе ассистента есть идентификаторы, которых нет в базе знаний: "
            f"{', '.join(unknown)}.\n\n"
            f"Исходный ответ:\n{text}\n\n"
            "Замени несуществующие идентификаторы на корректные из списка ниже "
            "или убери их. Верни только исправленный ответ на русском, без пояснений.\n"
            f"Разрешённые идентификаторы: {allowed}"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты исправляешь системные идентификаторы в ответе. "
                    "Не добавляй новые факты, не меняй смысл."
                ),
            },
            {"role": "user", "content": request},
        ]
        return "".join(self.backend.chat(messages, max_tokens=512)).strip()

    def answer(self, question: str, cancel_event: threading.Event | None = None) -> AnswerResult:
        question = question.strip()
        if not question:
            raise ValueError("Пустой запрос")

        built = build_messages(question, self.pack, self.template)
        started = time.perf_counter()
        deadline = started + self.settings.llm_timeout_s
        chunks: list[str] = []

        for piece in self.backend.chat(
            built.messages, max_tokens=self.settings.llm_max_output_tokens
        ):
            if cancel_event is not None and cancel_event.is_set():
                raise Cancelled
            if time.perf_counter() > deadline:
                raise LLMTimeout("Превышено время ожидания ответа")
            chunks.append(piece)

        raw_text = "".join(chunks).strip()
        stats: LLMStats = self.backend.last_stats
        validation: ValidationResult = validate_answer(raw_text, repair=self._repair)
        latency_ms = (time.perf_counter() - started) * 1000
        sources = self._sources_for(validation.text)

        result = AnswerResult(
            text=validation.text,
            model=self.settings.llm_model,
            prompt_version=self.prompt_version,
            pack_version=self.pack_version,
            sources=sources,
            prompt_tokens=stats.prompt_tokens,
            output_tokens=stats.output_tokens,
            latency_ms=round(latency_ms, 1),
            validation_removed=validation.removed,
            hallucinated=validation.hallucinated,
            knowledge_source=self.knowledge_source,
        )
        self._write_log(question, result, built)
        return result

    def _write_log(self, question: str, result: AnswerResult, built: PromptBuildResult) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action_addr": "",
            "question": question,
            "answer": result.text,
            "model": self.settings.llm_backend + "/" + result.model,
            "prompt_version": result.prompt_version,
            "pack_version": result.pack_version,
            "latency_ms": result.latency_ms,
            "prompt_tokens": result.prompt_tokens,
            "output_tokens": result.output_tokens,
            "validation_removed": result.validation_removed,
            "knowledge_source": result.knowledge_source,
            "prompt_estimated_tokens": built.system_tokens,
        }
        path: Path = self.settings.dialog_log_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_lock, path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Не удалось записать dialog.jsonl: %s", exc)

    def health(self) -> dict[str, Any]:
        model_available = True
        if hasattr(self.backend, "model_available"):
            model_available = bool(self.backend.model_available())
        return {
            "llm": {
                "backend": self.settings.llm_backend,
                "model": self.settings.llm_model,
                "reachable": self.backend.health(),
                "model_available": model_available,
            },
            "kb": {
                "connected": self.kb_status.connected,
                "knowledgeSource": self.knowledge_source,
                "packVersion": self.pack_version,
                "degraded": bool(self.pack.get("degraded")),
                "partial": self.kb_status.partial,
                "missing": self.kb_status.missing,
                "counts": self.kb_status.counts,
                "errors": self.kb_status.errors,
            },
            "sc_connected": self.kb_status.connected,
            "knowledge_source": self.knowledge_source,
            "pack_version": self.pack_version,
            "prompt_version": self.prompt_version,
            "prompt_estimated_tokens": self._prompt.system_tokens,
            "knowledge_estimated_tokens": self._prompt.knowledge_tokens,
        }

    def close(self) -> None:
        close = getattr(self.backend, "close", None)
        if callable(close):
            close()
        if self.knowledge_source == "kb" and self.settings.assistant_transport == "direct-http":
            close_kb()
