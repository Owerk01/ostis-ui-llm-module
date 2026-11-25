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
IDENTIFIER_RE = re.compile(
    r"\b(?:(?:concept|nrel|rrel|action)_[A-Za-z0-9_\u0400-\u04FF]+|ui_[a-z0-9_]+)\b"
)
# Идентификаторы экземпляра (`ex_login`, `ex_login_cmp_10`, `cmp_999`) не имеют
# статического whitelist: разрешены только реально прочитанные из БЗ в запросе.
INSTANCE_ID_RE = re.compile(
    r"\b(?:ex_[A-Za-z0-9_\u0400-\u04FF]+|(?:[A-Za-z0-9]+_)?cmp_[A-Za-z0-9_\u0400-\u04FF]+)\b",
    re.IGNORECASE,
)
COMPONENT_ID_RE = re.compile(r"(?:^|_)cmp_", re.IGNORECASE)
REMOVAL_NOTE = "[часть ответа удалена: неизвестные идентификаторы]"

RepairCallback = Callable[[str, list[str]], str]


@dataclass
class UnknownIds:
    """Неизвестные id раздельно по двум классам — для метрик eval."""

    catalog: list[str] = field(default_factory=list)
    instance: list[str] = field(default_factory=list)

    @property
    def all(self) -> list[str]:
        return [*self.catalog, *self.instance]


@dataclass
class ValidationResult:
    text: str
    unknown_before: list[str] = field(default_factory=list)
    unknown_after: list[str] = field(default_factory=list)
    repair_attempted: bool = False
    removed: list[str] = field(default_factory=list)
    note_added: bool = False
    unknown_catalog_before: list[str] = field(default_factory=list)
    unknown_instance_before: list[str] = field(default_factory=list)
    unknown_catalog_after: list[str] = field(default_factory=list)
    unknown_instance_after: list[str] = field(default_factory=list)

    @property
    def hallucinated(self) -> bool:
        return bool(self.unknown_before)


def extract_identifiers(text: str) -> list[str]:
    return IDENTIFIER_RE.findall(text)


def extract_instance_ids(text: str) -> list[str]:
    return INSTANCE_ID_RE.findall(text)


def is_component_id(identifier: str) -> bool:
    """`ex_login_cmp_10` — компонент; `ex_login` — интерфейс."""
    return bool(COMPONENT_ID_RE.search(identifier))


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def find_unknown_by_class(
    text: str,
    whitelist: set[str] | None = None,
    instance_ids: set[str] | None = None,
) -> UnknownIds:
    """Разделяет выдуманные id каталога и id экземпляра.

    `instance_ids` — множество id, прочитанное из БЗ в этом запросе
    (интерфейс + видимые компоненты). Пользовательские `ex_*` из вопроса
    добавляет сервис: это цитата вопроса, но не основание ответа.
    """
    allowed = whitelist if whitelist is not None else ALLOWED_IDENTIFIERS
    allowed_instances = instance_ids or set()
    unknown = UnknownIds()
    for identifier in extract_identifiers(text):
        # rrel_1..10 — стандартные, rrel_11+ генерирует dialog_store для длинных
        # диалогов; оба варианта являются допустимыми ролевыми узлами.
        generated_role = identifier.startswith("rrel_") and identifier[5:].isdigit()
        if identifier not in allowed and not generated_role:
            unknown.catalog.append(identifier)
    for identifier in extract_instance_ids(text):
        if identifier not in allowed_instances:
            unknown.instance.append(identifier)
    unknown.catalog = _unique(unknown.catalog)
    unknown.instance = _unique(unknown.instance)
    return unknown


def find_unknown(
    text: str,
    whitelist: set[str] | None = None,
    instance_ids: set[str] | None = None,
) -> list[str]:
    return find_unknown_by_class(text, whitelist, instance_ids).all


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
    instance_ids: set[str] | None = None,
) -> ValidationResult:
    unknown = find_unknown_by_class(text, whitelist, instance_ids)
    if not unknown.all:
        return ValidationResult(text=text)

    logger.warning("В ответе неизвестные идентификаторы: %s", ", ".join(unknown.all))
    repaired_text = text
    repair_attempted = False
    # Без repair-колбэка считаем, что исправить не удалось: идентификаторы
    # будут вырезаны ниже, а не оставлены в ответе.
    after = unknown

    if repair is not None:
        repair_attempted = True
        try:
            repaired_text = repair(text, unknown.all)
            after = find_unknown_by_class(repaired_text, whitelist, instance_ids)
        except Exception as exc:  # repair не должен ломать основной ответ
            logger.warning("Repair-запрос не удался: %s", exc)
            repaired_text = text
            after = unknown

    if not after.all:
        return ValidationResult(
            text=repaired_text,
            unknown_before=unknown.all,
            repair_attempted=repair_attempted,
            unknown_catalog_before=unknown.catalog,
            unknown_instance_before=unknown.instance,
        )

    to_remove = _unique([*after.all, *unknown.all])
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
        unknown_before=unknown.all,
        unknown_after=after.all,
        repair_attempted=repair_attempted,
        removed=to_remove,
        note_added=note_added,
        unknown_catalog_before=unknown.catalog,
        unknown_instance_before=unknown.instance,
        unknown_catalog_after=after.catalog,
        unknown_instance_after=after.instance,
    )
