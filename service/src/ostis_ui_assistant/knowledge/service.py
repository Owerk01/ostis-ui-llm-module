"""Сервис ответа: knowledge pack + LLM + пост-валидация."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..config import Settings
from ..llm.base import LLMBackend, LLMError, LLMStats, LLMTimeout, create_backend
from ..sc.service_state import CONTRACT_VERSION, STATE_STARTING, lease_is_live
from .history import prepare_history
from .identifiers import ALL_IDENTIFIERS, ENVIRONMENT_IDENTIFIERS, PROPERTY_KEYS
from .instance import InstanceContext
from .kb_reader import KbStatus, close as close_kb, load_pack_from_kb
from .language import contains_prompt_disclosure, refusal_text
from .tokens import near_context_limit
from .render import (
    PromptBuildResult,
    build_messages,
    build_prompt,
    load_pack,
    load_template,
    sanitize_question,
)
from .validate import (
    ValidationResult,
    extract_identifiers,
    extract_instance_ids,
    find_unknown_by_class,
    is_component_id,
    validate_answer,
)

if TYPE_CHECKING:
    from ..sc.service_state import ServiceState

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
    repair_ms: float = 0.0
    tokens_unavailable: bool = False
    token_budget_warning: bool = False
    unknown_in_final: list[str] = field(default_factory=list)
    unknown_in_final_catalog: list[str] = field(default_factory=list)
    unknown_in_final_instance: list[str] = field(default_factory=list)
    knowledge_source: str = "fallback"
    guard: str = ""
    instance_tokens: int = 0
    instance_shown: int = 0
    instance_total: int = 0
    instance_truncated: bool = False
    history_messages: int = 0
    history_tokens: int = 0
    history_truncated: bool = False


class KnowledgeService:
    def __init__(
        self,
        settings: Settings,
        backend: LLMBackend | None = None,
        state: "ServiceState | None" = None,
    ) -> None:
        self.settings = settings
        self._state = state
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
        self._source_aliases = {
            identifier: "ui_env_html_representation" for identifier in ENVIRONMENT_IDENTIFIERS
        }

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
        for section in ("principles", "methodology_stages", "environment_notes"):
            for item in self.pack.get(section, []):
                result[item["idtf"]] = item.get("title_ru", item["idtf"])
        # Идентификаторы HTML-трансляции упоминаются в тексте заметки, но не совпадают
        # с её idtf: без явного соответствия ответ не получил бы основание.
        for identifier in ENVIRONMENT_IDENTIFIERS:
            result[identifier] = "HTML-представление компонентов"
        return result

    def _sources_for(
        self, text: str, context: InstanceContext | None = None
    ) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        seen: set[str] = set()
        for identifier in extract_identifiers(text):
            if identifier not in self._source_map:
                continue
            source_idtf = self._source_aliases.get(identifier, identifier)
            if source_idtf in seen:
                continue
            seen.add(source_idtf)
            sources.append({"idtf": source_idtf, "labelRu": self._source_map[identifier]})

        # Основания-экземпляры — наравне с каталогом: упомянутый в ответе id
        # становится основанием, только если узел реально прочитан из БЗ.
        if context is not None and context.mode != "none":
            nodes = context.source_idtfs
            for identifier in extract_instance_ids(text):
                if identifier not in nodes or identifier in seen:
                    continue
                seen.add(identifier)
                label = (
                    "компонент интерфейса"
                    if is_component_id(identifier)
                    else "экземпляр интерфейса"
                )
                sources.append({"idtf": identifier, "labelRu": label})
        return sources

    @staticmethod
    def _allowed_instance_ids(
        question: str, context: InstanceContext | None
    ) -> set[str]:
        """Id, которые модель вправе упомянуть: прочитанные + цитата вопроса.

        Классы каталога проверяются по статическому whitelist, а id экземпляра —
        только по прочитанному в этом запросе. `ex_*` из вопроса не считается
        выдумкой модели, но без чтения из БЗ не попадает в основания. `cmp_*`
        без прочитанного экземпляра вырезается всегда.
        """
        result = set(context.instance_ids) if context and context.mode != "none" else set()
        result.update(
            identifier
            for identifier in extract_instance_ids(question)
            if not is_component_id(identifier)
        )
        return result

    def _repair(
        self,
        text: str,
        unknown: list[str],
        *,
        deadline: float | None = None,
        cancel_event: threading.Event | None = None,
        instance_ids: set[str] | None = None,
    ) -> str:
        """Один repair-запрос, ограниченный тем же дедлайном и отменой."""
        if cancel_event is not None and cancel_event.is_set():
            return text
        if deadline is not None and time.perf_counter() >= deadline:
            return text

        allowed_ids = ALL_IDENTIFIERS | PROPERTY_KEYS | (instance_ids or set())
        allowed = ", ".join(sorted(allowed_ids))
        request = (
            "В ответе ассистента есть идентификаторы, которых нет в базе знаний: "
            f"{', '.join(unknown)}.\n\n"
            f"Исходный ответ:\n{text}\n\n"
            "Замени несуществующие идентификаторы на корректные из списка ниже "
            "или убери их. Верни только исправленный ответ на языке исходного, "
            "без пояснений.\n"
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
        pieces: list[str] = []
        for piece in self.backend.chat(messages, max_tokens=512):
            if cancel_event is not None and cancel_event.is_set():
                return text
            if deadline is not None and time.perf_counter() >= deadline:
                return text
            pieces.append(piece)
        return "".join(pieces).strip()

    def answer(
        self,
        question: str,
        cancel_event: threading.Event | None = None,
        context: InstanceContext | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> AnswerResult:
        question = question.strip()
        if not question:
            raise ValueError("Пустой запрос")

        # Неизвестные идентификаторы в вопросе заменяются, но вопрос доходит до LLM.
        # Детерминированный отказ — только если после санитизации не осталось смысла.
        prompt_question = sanitize_question(question)
        guard = "sanitized" if prompt_question != question else ""
        if guard:
            remainder = prompt_question.replace("«неизвестный идентификатор»", "")
            remainder = remainder.strip(" \t\n,.;:!?-—")
            if len(remainder) < 3:
                built = build_messages(question, self.pack, self.template)
                result = AnswerResult(
                    text=refusal_text("unknown_id", question),
                    model=self.settings.llm_model,
                    prompt_version=self.prompt_version,
                    pack_version=self.pack_version,
                    knowledge_source=self.knowledge_source,
                    guard="unknown_identifier",
                )
                self._write_log(question, result, built)
                return result

        prompt_history = prepare_history(history or [], self.settings.dialog_history_turns)
        built = build_messages(
            prompt_question,
            self.pack,
            self.template,
            budget=self.settings.knowledge_token_budget,
            context=context,
            instance_budget=self.settings.instance_token_budget,
            history=prompt_history,
            history_budget=self.settings.history_token_budget,
            language_question=question,
        )
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
        token_warning = near_context_limit(stats.prompt_tokens, self.settings.llm_num_ctx)
        if token_warning:
            logger.warning(
                "Фактический промпт %s токенов занимает >80%% контекста %s; "
                "оценка рендера — %s",
                stats.prompt_tokens,
                self.settings.llm_num_ctx,
                built.knowledge_tokens,
            )
        # Утечка служебных правил не должна доходить до пользователя даже если
        # модель нарушила правило 13 промпта.
        if contains_prompt_disclosure(raw_text):
            result = AnswerResult(
                text=refusal_text("policy", question),
                model=self.settings.llm_model,
                prompt_version=self.prompt_version,
                pack_version=self.pack_version,
                prompt_tokens=stats.prompt_tokens,
                output_tokens=stats.output_tokens,
                latency_ms=round((time.perf_counter() - started) * 1000, 1),
                tokens_unavailable=stats.tokens_unavailable,
                token_budget_warning=token_warning,
                knowledge_source=self.knowledge_source,
                guard="policy",
            )
            self._write_log(question, result, built)
            return result

        repair_times: list[float] = []
        allowed_instances = self._allowed_instance_ids(question, context)
        read_instances = context.instance_ids if context and context.mode != "none" else set()

        def repair(text: str, unknown: list[str]) -> str:
            repair_started = time.perf_counter()
            try:
                return self._repair(
                    text,
                    unknown,
                    deadline=deadline,
                    cancel_event=cancel_event,
                    instance_ids=read_instances,
                )
            finally:
                repair_times.append((time.perf_counter() - repair_started) * 1000)

        validation: ValidationResult = validate_answer(
            raw_text, repair=repair, instance_ids=allowed_instances
        )
        latency_ms = (time.perf_counter() - started) * 1000
        sources = self._sources_for(validation.text, context)
        final_unknown = find_unknown_by_class(validation.text, instance_ids=allowed_instances)

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
            repair_ms=round(sum(repair_times), 1),
            tokens_unavailable=stats.tokens_unavailable,
            token_budget_warning=token_warning,
            unknown_in_final=final_unknown.all,
            unknown_in_final_catalog=final_unknown.catalog,
            unknown_in_final_instance=final_unknown.instance,
            knowledge_source=self.knowledge_source,
            guard=guard,
            instance_tokens=built.instance_tokens,
            instance_shown=built.instance_shown,
            instance_total=built.instance_total,
            instance_truncated=built.instance_truncated,
            history_messages=len(prompt_history),
            history_tokens=built.history_tokens,
            history_truncated=built.history_truncated,
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
            "contract_version": CONTRACT_VERSION,
            "pack_version": result.pack_version,
            "latency_ms": result.latency_ms,
            "repair_ms": result.repair_ms,
            "prompt_tokens": result.prompt_tokens,
            "output_tokens": result.output_tokens,
            "tokens_unavailable": result.tokens_unavailable,
            "token_budget_warning": result.token_budget_warning,
            "validation_removed": result.validation_removed,
            "unknown_in_final": result.unknown_in_final,
            "unknown_in_final_catalog": result.unknown_in_final_catalog,
            "unknown_in_final_instance": result.unknown_in_final_instance,
            "knowledge_source": result.knowledge_source,
            "prompt_estimated_tokens": built.system_tokens,
            "instance_tokens": result.instance_tokens,
            "instance_components_shown": result.instance_shown,
            "instance_components_total": result.instance_total,
            "instance_truncated": result.instance_truncated,
            "history_messages": result.history_messages,
            "history_tokens": result.history_tokens,
            "history_truncated": result.history_truncated,
            "history_turns_limit": self.settings.dialog_history_turns,
            "guard": result.guard,
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

        snapshot = self._state.snapshot() if self._state is not None else None
        ttl = self.settings.service_lease_ttl_s
        now = datetime.now(timezone.utc)

        schema_loaded = bool(self.kb_status.connected)
        agent_alive = False
        service_state = STATE_STARTING
        queue_depth = 0
        contract_version = CONTRACT_VERSION
        model = self.settings.llm_model
        pack_version = self.pack_version
        prompt_version = self.prompt_version
        knowledge_source = self.knowledge_source

        if snapshot is not None:
            agent_alive = lease_is_live(
                snapshot,
                snapshot.get("heartbeat_at"),
                ttl_s=ttl,
                now=now,
            )
            service_state = str(snapshot.get("state", STATE_STARTING))
            queue_depth = int(snapshot.get("queue_size", 0) or 0)
            contract_version = str(snapshot.get("contract_version", CONTRACT_VERSION))
            model = str(snapshot.get("model", self.settings.llm_model))
            pack_version = str(snapshot.get("pack_version", self.pack_version))
            prompt_version = str(snapshot.get("prompt_version", self.prompt_version))
            knowledge_source = str(snapshot.get("knowledge_source", self.knowledge_source))

        return {
            "llm": {
                "backend": self.settings.llm_backend,
                "model": model,
                "reachable": self.backend.health(),
                "model_available": model_available,
            },
            "kb": {
                "connected": self.kb_status.connected,
                "knowledgeSource": knowledge_source,
                "packVersion": pack_version,
                "degraded": bool(self.pack.get("degraded")),
                "partial": self.kb_status.partial,
                "missing": self.kb_status.missing,
                "counts": self.kb_status.counts,
                "errors": self.kb_status.errors,
            },
            "schemaLoaded": schema_loaded,
            "agentAlive": agent_alive,
            "state": service_state,
            "model": model,
            "packVersion": pack_version,
            "promptVersion": prompt_version,
            "knowledgeSource": knowledge_source,
            "queueDepth": queue_depth,
            "contractVersion": contract_version,
            "sc_connected": self.kb_status.connected,
            "knowledge_source": knowledge_source,
            "pack_version": pack_version,
            "prompt_version": prompt_version,
            "prompt_estimated_tokens": self._prompt.system_tokens,
            "knowledge_estimated_tokens": self._prompt.knowledge_tokens,
            "timeouts": {
                "llmTimeoutS": self.settings.llm_timeout_s,
                "dialogClientTimeoutS": self.settings.dialog_client_timeout_s,
            },
            "tokenBudgets": {
                "knowledge": self.settings.knowledge_token_budget,
                "history": self.settings.history_token_budget,
                "instance": self.settings.instance_token_budget,
                "outputReserve": self.settings.output_reserve_tokens,
                "historyTurns": self.settings.dialog_history_turns,
            },
        }

    def close(self) -> None:
        close = getattr(self.backend, "close", None)
        if callable(close):
            close()
        if self.knowledge_source == "kb" and self.settings.assistant_transport == "direct-http":
            close_kb()
