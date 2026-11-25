"""Тесты пост-валидации идентификаторов."""

from __future__ import annotations

from pathlib import Path

from ostis_ui_assistant.knowledge.validate import (
    REMOVAL_NOTE,
    extract_identifiers,
    find_unknown,
    validate_answer,
)

ROOT = Path(__file__).resolve().parents[2]


def test_known_identifiers_pass_untouched() -> None:
    text = "`concept_ui_button` связан с `nrel_ui_contains` и свойством `action_id`."
    result = validate_answer(text)
    assert result.text == text
    assert result.hallucinated is False


def test_property_key_action_id_is_not_hallucination() -> None:
    # `action_id` совпадает с префиксом action_*, но это ключ свойства.
    result = validate_answer("Действие задаётся свойством action_id.")
    assert result.hallucinated is False
    assert result.text == "Действие задаётся свойством action_id."


def test_invented_identifier_is_detected() -> None:
    text = "В каталоге есть `concept_ui_gantt_chart`."
    assert find_unknown(text) == ["concept_ui_gantt_chart"]
    result = validate_answer(text)
    assert result.hallucinated is True


def test_cyrillic_substitution_is_detected() -> None:
    assert find_unknown("компонент `concept_ui_кнопка`") == ["concept_ui_кнопка"]


def test_wrong_case_is_detected() -> None:
    assert find_unknown("`concept_ui_Button`") == ["concept_ui_Button"]


def test_russian_word_inside_identifier_is_detected() -> None:
    assert find_unknown("`nrel_ui_содержит`") == ["nrel_ui_содержит"]


def test_repair_success_keeps_fixed_answer() -> None:
    def repair(text: str, unknown: list[str]) -> str:
        assert unknown == ["concept_ui_gantt_chart"]
        return text.replace("concept_ui_gantt_chart", "concept_ui_list")

    result = validate_answer(
        "В каталоге есть `concept_ui_gantt_chart`.", repair=repair
    )
    assert result.repair_attempted is True
    assert result.text == "В каталоге есть `concept_ui_list`."
    assert result.unknown_before == ["concept_ui_gantt_chart"]
    assert result.unknown_after == []
    assert result.hallucinated is True


def test_repair_failure_removes_identifiers_and_marks() -> None:
    text = "В каталоге есть `concept_ui_gantt_chart` и `concept_ui_button`."
    result = validate_answer(text, repair=lambda original, unknown: original)

    assert result.removed == ["concept_ui_gantt_chart"]
    assert "concept_ui_gantt_chart" not in result.text
    assert "concept_ui_button" in result.text
    assert REMOVAL_NOTE in result.text
    assert result.note_added is True


def test_repair_exception_does_not_break_answer() -> None:
    def repair(text: str, unknown: list[str]) -> str:
        raise RuntimeError("LLM недоступна")

    result = validate_answer("`concept_ui_fake` — несуществующий тип.", repair=repair)
    assert result.repair_attempted is True
    assert "concept_ui_fake" not in result.text
    assert REMOVAL_NOTE in result.text


def test_no_repair_removes_unknown() -> None:
    result = validate_answer("Тип `concept_ui_fake` не существует.")
    assert "concept_ui_fake" not in result.text
    assert REMOVAL_NOTE in result.text


def test_extract_ignores_plain_russian_words() -> None:
    assert extract_identifiers("Кнопка и пункт меню — это компоненты.") == []


def test_generated_role_identifiers_allowed() -> None:
    """rrel_11+ создаются нами для длинных диалогов и не считаются галлюцинацией."""
    assert find_unknown("роль `rrel_11` задаёт порядок сообщения") == []


def test_unknown_knowledge_identifier_removed() -> None:
    """Выдуманные ui_*-ссылки на несуществующие узлы знаний вырезаются."""
    result = validate_answer("См. раздел ui_fake_section.")

    assert "ui_fake_section" not in result.text
    assert REMOVAL_NOTE in result.text


def test_environment_identifier_allowed() -> None:
    """Идентификаторы HTML-трансляции упоминаются, но не считаются галлюцинацией."""
    text = "Трансляцию выполняет `action_translate_sc_to_html`, результат хранит `nrel_html_representation`."
    assert find_unknown(text) == []
    assert validate_answer(text).unknown_after == []


def test_no_stale_environment_identifiers() -> None:
    """Удалённые из keynodes имена не возвращаются ни в whitelist, ни в знания."""
    from ostis_ui_assistant.knowledge.identifiers import (
        ALL_IDENTIFIERS,
        ENVIRONMENT_IDENTIFIERS,
        REMOVED_ENVIRONMENT_IDENTIFIERS,
    )

    assert not (ENVIRONMENT_IDENTIFIERS & REMOVED_ENVIRONMENT_IDENTIFIERS)
    assert not (ALL_IDENTIFIERS & REMOVED_ENVIRONMENT_IDENTIFIERS)
    for stale in REMOVED_ENVIRONMENT_IDENTIFIERS:
        assert find_unknown(f"`{stale}`") == [stale]
    texts = [
        (ROOT / "knowledge" / "pack.json").read_text(encoding="utf-8"),
        (ROOT / "knowledge" / "purpose_overrides.json").read_text(encoding="utf-8"),
        (ROOT / "knowledge" / "prompt_v4.md").read_text(encoding="utf-8"),
        (ROOT / "kb" / "ui_assistant" / "ui_environment.scs").read_text(encoding="utf-8"),
        (
            ROOT
            / "kb"
            / "ui_assistant"
            / "generated"
            / "ui_catalog_knowledge.scs"
        ).read_text(encoding="utf-8"),
    ]
    for text in texts:
        for stale in REMOVED_ENVIRONMENT_IDENTIFIERS:
            assert stale not in text, stale
