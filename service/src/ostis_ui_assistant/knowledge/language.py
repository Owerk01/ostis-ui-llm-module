"""Язык ответа и защита от раскрытия внутренних правил ассистента.

Детерминированные отказы и пост-валидация не зависят от LLM: даже если модель
нарушит правило промпта, пользователь не увидит служебные инструкции.
"""

from __future__ import annotations

import re

_RU = re.compile(r"[\u0400-\u04ff]")
_EN = re.compile(r"[A-Za-z]")
# Системные идентификаторы не должны перевешивать язык самого вопроса.
_ID_TOKEN_RE = re.compile(
    r"\b(?:(?:concept|nrel|rrel|action|ex|ui)_[A-Za-z0-9_\u0400-\u04ff]+"
    r"|(?:[A-Za-z0-9]+_)?cmp_[A-Za-z0-9_\u0400-\u04ff]+)\b",
    re.IGNORECASE,
)

_REFUSALS: dict[str, dict[str, str]] = {
    "unknown_id": {
        "ru": (
            "В базе знаний среды нет сведений об указанном идентификаторе: его нет в "
            "каталоге, и я не создаю новые компоненты. Могу ответить о типах "
            "компонентов, их свойствах, принципах разработки, методике или "
            "устройстве среды."
        ),
        "en": (
            "The knowledge base has no information about that identifier: it is not in "
            "the catalog, and I do not invent components. I can answer questions about "
            "component types, their properties, development principles, methodology, "
            "or the environment."
        ),
    },
    "policy": {
        "ru": (
            "Я не рассказываю о своих внутренних правилах и настройках. Могу ответить "
            "на вопрос по каталогу компонентов, их свойствам, принципам разработки, "
            "методике или устройству среды."
        ),
        "en": (
            "I do not disclose my internal rules or prompt. I can answer questions "
            "about the component catalog, properties, development principles, "
            "methodology, or the environment."
        ),
    },
}

# Служебные формулировки из системного промпта и типичные попытки его пересказать.
# Регистр важен для «ЗНАНИЯ»: «блок знаний» — нормальная фраза ответа, а не утечка.
_DISCLOSURE_PATTERNS: tuple[tuple[str, int | None], ...] = (
    (r"\bсистемн(?:ый|ого|ому|ым)?\s+промпт\b", re.IGNORECASE),
    (r"\bsystem\s+prompt\b", re.IGNORECASE),
    (r"\bвнутренн(?:ие|их|им|яя|ей)\s+правил\w*\b", re.IGNORECASE),
    (r"\binternal\s+(?:rules|instructions|prompt)\b", re.IGNORECASE),
    (r"\bмо(?:и|их|им|я)\s+правил\w*\b", re.IGNORECASE),
    (r"\bmy\s+(?:prompt|rules|instructions)\b", re.IGNORECASE),
    (r"\bв\s+мо(?:их|ей)\s+инструкци\w*\b", re.IGNORECASE),
    (r"\bсогласно\s+(?:моим|внутренним)\s+правилам\b", re.IGNORECASE),
    (r"\baccording\s+to\s+my\s+(?:rules|instructions)\b", re.IGNORECASE),
    (r"\bмне\s+(?:предписано|запрограммирован|сказано\s+в\s+промпте)\b", re.IGNORECASE),
    (r"\bi\s+am\s+(?:instructed|programmed|required\s+to)\b", re.IGNORECASE),
    (r"\bя\s+(?:должен|обязан|должна)\s+(?:отвечать|опираться|не\s+выдумывать)\b", re.IGNORECASE),
    (r"\bi\s+(?:must|have\s+to)\s+(?:answer|rely\s+on|follow)\b", re.IGNORECASE),
    (r"\bправил\w*\s+\d+\b", re.IGNORECASE),
    (r"\brule\s+\d+\b", re.IGNORECASE),
    (r"\bпункт\s+\d+\s+правил\b", re.IGNORECASE),
    (r"\bПЕРЕД\s+ОТВЕТОМ\s+ПРОВЕРЬ\b", None),
    (r"\bКРОМЕ\s+ТОГО\b", None),
    (r"\bОтвечай\s+на\s+языке\s+вопроса\b", None),
    (r"\bОпирайся\s+ТОЛЬКО\s+на\s+блок\s+ЗНАНИЯ\b", None),
    (r"\bблок\s+ЗНАНИЯ\b", None),
    (r"<\/?catalog_", None),
    (r"\{\{", None),
    (r"\bfew[- ]?shot\b", re.IGNORECASE),
)


def detect_language(text: str) -> str:
    """Грубая языковая метка для детерминированных ответов: ``ru`` или ``en``.

    Для остальных языков LLM сама подстраивается под вопрос (правило 1 промпта),
    а детерминированные отказы по умолчанию даются на английском.
    """
    words = _ID_TOKEN_RE.sub(" ", text)
    # Вопрос из одного идентификатора языка не имеет — сохраняем русский fallback.
    cyrillic = len(_RU.findall(words))
    latin = len(_EN.findall(words))
    return "ru" if cyrillic >= latin else "en"


LANGUAGE_DIRECTIVE = (
    "Answer in exactly the same natural language as the user's question. "
    "The knowledge block and the examples are in Russian, but they do not "
    "determine the answer language: do not answer in Russian unless the "
    "question is in Russian. Keep all concept_ui_*, nrel_ui_* and property "
    "keys verbatim."
)


def language_directive(question: str) -> str | None:
    """Дополнительная инструкция перед вопросом, если он не на русском."""
    return None if detect_language(question) == "ru" else LANGUAGE_DIRECTIVE


def refusal_text(kind: str, question: str) -> str:
    """Локализованный детерминированный ответ по языку вопроса."""
    variants = _REFUSALS.get(kind)
    if variants is None:
        raise ValueError(f"Неизвестный вид отказа: {kind}")
    return variants[detect_language(question)]


def contains_prompt_disclosure(text: str) -> bool:
    """True, если ответ пересказывает внутренние правила или служебный промпт."""
    return any(
        re.search(pattern, text, flags or 0) is not None
        for pattern, flags in _DISCLOSURE_PATTERNS
    )
