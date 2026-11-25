"""T7: чтение экземпляра интерфейса не создаёт элементов в sc-памяти."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import MagicMock

from sc_client.constants import sc_type
from sc_client.models import ScAddr, ScTemplate

from ostis_ui_assistant.knowledge import instance as instance_module
from ostis_ui_assistant.knowledge.instance import ComponentData, InstanceContext, read_context, read_interface

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Row:
    values: dict[str, ScAddr]

    def get(self, alias: str) -> ScAddr:
        return self.values[alias]


class FakeKb:
    """Минимальный граф: узлы, связи, link-значения и системные идентификаторы."""

    def __init__(self) -> None:
        self.keynodes: dict[str, ScAddr] = {}
        self.relations: dict[tuple[int, str], list[ScAddr]] = {}
        self.links: dict[int, str] = {}
        self.identifiers: dict[int, str] = {}
        self.contents: dict[str, list[list[ScAddr]]] = {}
        self.properties: dict[tuple[int, int], str] = {}
        self._next = 1000

    def addr(self) -> ScAddr:
        self._next += 1
        return ScAddr(self._next)

    @staticmethod
    def addr_from_int(value: int) -> ScAddr:
        return ScAddr(value)

    def keynode(self, idtf: str) -> ScAddr:
        if idtf not in self.keynodes:
            self.keynodes[idtf] = self.addr()
            self.identifiers[self.keynodes[idtf].value] = idtf
        return self.keynodes[idtf]

    def link(self, value: str) -> ScAddr:
        addr = self.addr()
        self.links[addr.value] = value
        return addr

    def relate(self, source: ScAddr, idtf: str, target: ScAddr) -> None:
        self.relations.setdefault((source.value, idtf), []).append(target)
        self.keynode(idtf)

    def property(self, source: ScAddr, key: str, value: str) -> None:
        link = self.link(value)
        self.relate(source, "nrel_ui_value", link)
        self.properties[(source.value, link.value)] = key

    def search(self, template: ScTemplate) -> list[Row]:
        triples = template.triple_list
        if len(triples) == 2:
            first, second = triples
            source_value = getattr(first.source, "value", first.source)
            source_value = getattr(source_value, "value", source_value)
            if getattr(second.source, "alias", None) == "_property":
                source = source_value
                rows: list[Row] = []
                for (node, link), key in self.properties.items():
                    if node == source:
                        rows.append(
                            Row(
                                {
                                    "_value": self.addr_from_int(link),
                                    "_property": self.keynode(f"concept_ui_{key}"),
                                }
                            )
                        )
                return rows
            relation = self._relation_of(second.source.value)
            if relation and first.target.alias == "_target":
                return [
                    Row({"_target": target})
                    for target in self.relations.get((source_value, relation), [])
                ]
            if relation and first.target.value is not None:
                link_value = getattr(first.target.value, "value", first.target.value)
                return [
                    Row({"_node": self.addr_from_int(source)})
                    for (source, idtf), targets in self.relations.items()
                    if idtf == relation and any(link.value == link_value for link in targets)
                ]
        if len(triples) == 1 and triples[0].source.alias == "_class":
            component = getattr(triples[0].target.value, "value", triples[0].target.value)
            result: list[Row] = []
            for idtf, addr in self.keynodes.items():
                if idtf.startswith("concept_ui_") and any(
                    target.value == component
                    for (source, relation), targets in self.relations.items()
                    for target in targets
                    if source == addr.value and relation == "perm_pos"
                ):
                    result.append(Row({"_class": addr}))
            return result
        return []

    def _relation_of(self, value: object) -> str | None:
        numeric = getattr(value, "value", value)
        for idtf, addr in self.keynodes.items():
            if addr.value == numeric:
                return idtf
        return None


def _patch_client(monkeypatch, kb: FakeKb) -> None:
    monkeypatch.setattr(instance_module.ScKeynodes, "get", lambda idtf: kb.keynode(idtf))
    monkeypatch.setattr(instance_module, "search_by_template", kb.search)
    monkeypatch.setattr(
        instance_module, "search_links_by_contents", lambda value: kb.contents.get(value, [])
    )
    monkeypatch.setattr(
        instance_module, "get_link_content_data", lambda link: kb.links.get(link.value)
    )
    monkeypatch.setattr(
        instance_module,
        "get_element_system_identifier",
        lambda addr: kb.identifiers.get(addr.value),
    )


def test_read_context_reads_instance_without_generating(monkeypatch) -> None:
    kb = FakeKb()
    _patch_client(monkeypatch, kb)

    interface = kb.addr()
    button = kb.addr()
    field = kb.addr()
    kb.identifiers.update({interface.value: "ex_login", button.value: "ex_login_cmp_10", field.value: "ex_login_cmp_5"})
    kb.relate(kb.keynode("concept_ui_interface"), "perm_pos", interface)
    kb.relate(kb.keynode("concept_ui_button"), "perm_pos", button)
    kb.relate(kb.keynode("concept_ui_text_field"), "perm_pos", field)
    kb.relate(interface, "nrel_ui_has_component", button)
    kb.relate(interface, "nrel_ui_has_component", field)
    kb.relate(button, "nrel_ui_input_target", field)
    kb.relate(button, "nrel_ui_output_target", field)
    kb.relate(button, "nrel_ui_contains", field)
    kb.property(button, "text_value", "Войти")
    kb.property(button, "action_id", "auth_submit")

    context = kb.addr()
    kb.relate(context, "nrel_ui_context_mode", kb.link("selection"))
    kb.relate(context, "nrel_ui_context_interface", interface)
    kb.relate(context, "nrel_ui_context_component", button)
    kb.relate(kb.keynode("nrel_ui_id"), "perm_pos", kb.link("ex_login"))

    # Любая попытка записать в БЗ в read-пути observer_failures провалит тест.
    failures: list[str] = []
    for name in ("generate_node", "generate_link", "generate_connector", "generate_binary_relation"):
        def fail(*args, **kwargs) -> None:
            failures.append(name)
            raise AssertionError(f"read-путь вызвал {name}")
        monkeypatch.setattr(instance_module, name, fail, raising=False)

    result = read_context(context)

    assert failures == []
    assert result.mode == "selection"
    assert result.interface_id == "ex_login"
    assert result.selected_ids == {"ex_login_cmp_10"}
    assert {item.idtf for item in result.components} == {"ex_login_cmp_10", "ex_login_cmp_5"}
    button_data = next(item for item in result.components if item.idtf == "ex_login_cmp_10")
    assert button_data.sc_class == "concept_ui_button"
    assert button_data.properties == {"text_value": "Войти", "action_id": "auth_submit"}
    assert button_data.inputs == ["ex_login_cmp_5"]
    assert button_data.outputs == ["ex_login_cmp_5"]
    assert button_data.children == ["ex_login_cmp_5"]
    # selection: интерфейс + выделенный компонент, остальной интерфейс не раскрываем.
    assert len(result.source_addrs) == 2


def test_read_context_none_mode_is_empty() -> None:
    result = read_context(None)
    assert result == InstanceContext()
    assert result.source_addrs == []


def test_read_interface_by_ui_id(monkeypatch) -> None:
    kb = FakeKb()
    _patch_client(monkeypatch, kb)
    interface = kb.addr()
    id_link = kb.link("ex_login")
    kb.contents["ex_login"] = [[id_link]]
    kb.relations[(interface.value, "nrel_ui_id")] = [id_link]
    kb.identifiers[interface.value] = "ex_login"

    result = read_interface("ex_login", ["ex_login_cmp_10"])

    assert result.mode == "whole"
    assert result.interface_id == "ex_login"
    assert result.interface_addr is not None
    assert result.selected_ids == {"ex_login_cmp_10"}


def test_unknown_interface_returns_empty_context(monkeypatch) -> None:
    kb = FakeKb()
    _patch_client(monkeypatch, kb)
    monkeypatch.setattr(instance_module.ScKeynodes, "get", lambda idtf: None)

    result = read_interface("ex_missing")

    assert result.components == []
    assert result.interface_addr is None


def test_read_path_has_no_generation_or_resolve() -> None:
    source = (ROOT / "service" / "src" / "ostis_ui_assistant" / "knowledge" / "instance.py").read_text(
        encoding="utf-8"
    )
    assert not re.search(r"\bgenerate_\w+\s*\(", source)
    assert "ScKeynodes.resolve" not in source
    assert "sc_type.VAR_" in source  # шаблоны поиска, а не генерации


def test_component_data_is_lightweight() -> None:
    component = ComponentData(idtf="ex_login_cmp_10", sc_class="concept_ui_button")
    assert component.properties == {}
    assert component.addr is None
    assert component.inputs == []
