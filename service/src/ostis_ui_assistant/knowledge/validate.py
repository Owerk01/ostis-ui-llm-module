"""Пост-валидация идентификаторов в ответе LLM."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable

from .identifiers import ALL_IDENTIFIERS, PROPERTY_KEYS

logger = logging.getLogger(__name__)

# Разрешены существующие идентификаторы, наши новые и ключи свойств.
# Ключ `action_id` совпадает по префиксу с `action_*`, поэтому без PROPERTY_KEYS
# он ошибочно считался бы выдуманным идентификатором.
ALLOWED_IDENTIFIERS = ALL_IDENTIFIERS | PROPERTY_KEYS

# Ловим также верхний регистр и кириллицу внутри идентификатора, чтобы
# пометить такие подмены как неизвестные, а не молча пропустить.
IDENTIFIER_RE = re.compile(r"\b(?:concept|nrel|rrel|action)_[A-Za-z0-9_\u0400-\u04FF]+\b")
REMOVAL_NOTE = "[часть ответа удалена: неизвестные идентификаторы]"

RepairCallback = Callable[[str, list[str]], str]


@dataclass
class ValidationResult:
    text: str
    unknown_before: list[str] = field(default_factory=list)
    unknown_after: list[str] = field(default_factory=list)
    repair_attempted: bool = False
    removed: list[str] = field(default_factory=list)
    note_added: bool = False

    @property
    def hallucinated(self) -> bool:
        return bool(self.unknown_before)


def extract_identifiers(text: str) -> list[str]:
    return IDENTIFIER_RE.findall(text)


def find_unknown(
    text: str, whitelist: set[str] | None = None
) -> list[str]:
    allowed = whitelist if whitelist is not None else ALLOWED_IDENTIFIERS
    seen: dict[str, None] = {}
    for identifier in extract_identifiers(text):
        if identifier not in allowed:
            seen.setdefault(identifier, None)
    return list(seen)


def _remove_identifiers(text: str, identifiers: list[str]) -> str:
    result = text
    for identifier in identifiers:
        pattern = re.compile(
            rf"(?<![A-Za-z0-9_])`?{re.escape(identifier)}`?(?![A-Za-z0-9_])"
        )
        result = pattern.sub("", result)
    result = re.sub(r"``+", "", result)
    result = re.sub(r"[ \t]{2,}", " ", result)
    result = re.sub(r" +([,.;:!?])", r"\1", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def validate_answer(
    text: str,
    *,
    repair: RepairCallback | None = None,
    whitelist: set[str] | None = None,
) -> ValidationResult:
    unknown_before = find_unknown(text, whitelist)
    if not unknown_before:
        return ValidationResult(text=text)

    logger.warning("В ответе неизвестные идентификаторы: %s", ", ".join(unknown_before))
    repaired_text = text
    repair_attempted = False
    # Без repair-колбэка считаем, что исправить не удалось: идентификаторы
    # будут вырезаны ниже, а не оставлены в ответе.
    unknown_after: list[str] = list(unknown_before)

    if repair is not None:
        repair_attempted = True
        try:
            repaired_text = repair(text, unknown_before)
            unknown_after = find_unknown(repaired_text, whitelist)
        except Exception as exc:  # repair не должен ломать основной ответ
            logger.warning("Repair-запрос не удался: %s", exc)
            repaired_text = text
            unknown_after = unknown_before

    if not unknown_after:
        return ValidationResult(
            text=repaired_text,
            unknown_before=unknown_before,
            repair_attempted=repair_attempted,
        )

    to_remove = unknown_after or unknown_before
    stripped = _remove_identifiers(repaired_text, to_remove)
    note_added = False
    if REMOVAL_NOTE not in stripped:
        stripped = f"{stripped}\n\n{REMOVAL_NOTE}".strip()
        note_added = True

    logger.error(
        "После repair остались неизвестные идентификаторы: %s; они удалены",
        ", ".join(to_remove),
    )
    return ValidationResult(
        text=stripped,
        unknown_before=unknown_before,
        unknown_after=unknown_after,
        repair_attempted=repair_attempted,
        removed=to_remove,
        note_added=note_added,
    )
