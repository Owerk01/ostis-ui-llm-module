"""Чтение экземпляра интерфейса из sc-памяти.

Только чтение: используются `ScKeynodes.get()` (без создания узла) и
`search_by_template`. Ни один generate_* здесь не вызывается — запрос к
конкретному интерфейсу не должен изменить БЗ.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Iterable

from sc_client.client import search_by_template, search_links_by_contents
from sc_client.constants import sc_type
from sc_client.models import ScAddr, ScTemplate
from sc_kpm import ScKeynodes
from sc_kpm.utils import get_element_system_identifier, get_link_content_data

from .identifiers import COMPONENT_CLASSES, PROPERTY_KEYS

logger = logging.getLogger(__name__)

CONTEXT_MODES = ("none", "selection", "whole")
COMPOSED_REL = "nrel_ui_has_component"
CONTAINS_REL = "nrel_ui_contains"
INPUT_REL = "nrel_ui_input_target"
OUTPUT_REL = "nrel_ui_output_target"


@dataclass
class ComponentData:
    """Один компонент прочитанного интерфейса."""

    idtf: str
    sc_class: str = ""
    properties: dict[str, str] = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    addr: Any = None


@dataclass
class InstanceContext:
    """Экземпляр, который баннер запроса передал агенту через rrel_3."""

    mode: str = "none"
    interface_id: str | None = None
    components: list[ComponentData] = field(default_factory=list)
    selected_ids: set[str] = field(default_factory=set)
    interface_addr: Any = None
    selected_addrs: list[Any] = field(default_factory=list)

    @property
    def visible_components(self) -> list[ComponentData]:
        """Компоненты, которые реально попали в промпт (selection — только выделенные)."""
        if self.mode == "selection":
            return [item for item in self.components if item.idtf in self.selected_ids]
        return list(self.components)

    @property
    def instance_ids(self) -> set[str]:
        """Id, которые валидатор вправе считать прочитанными из БЗ в этом запросе."""

        def valid(addr: Any) -> bool:
            return addr is not None and getattr(addr, "is_valid", lambda: False)()

        result = {self.interface_id} if self.interface_id and valid(self.interface_addr) else set()
        result.update(
            item.idtf
            for item in self.visible_components
            if item.idtf and valid(item.addr)
        )
        return result

    @property
    def source_idtfs(self) -> dict[str, Any]:
        """Соответствие id прочитанного экземпляра узлам БЗ для оснований ответа."""
        result: dict[str, Any] = {}
        candidates = [(self.interface_id, self.interface_addr)]
        candidates.extend((item.idtf, item.addr) for item in self.visible_components)
        for idtf, addr in candidates:
            if idtf and addr is not None and getattr(addr, "is_valid", lambda: False)():
                result[idtf] = addr
        return result

    @property
    def source_addrs(self) -> list[Any]:
        """Узлы БЗ, на которые можно сослаться как на основания ответа."""
        result: list[Any] = []
        seen: set[int] = set()
        for addr in [
            self.interface_addr,
            *self.selected_addrs,
            *(c.addr for c in self.visible_components),
        ]:
            if addr is None or not getattr(addr, "is_valid", lambda: False)():
                continue
            key = int(addr.value)
            if key not in seen:
                seen.add(key)
                result.append(addr)
        return result


class _Reader:
    """Набор read-only шаблонов; keynodes кешируются на один запрос."""

    def __init__(self) -> None:
        self._keynodes: dict[str, ScAddr | None] = {}

    def keynode(self, idtf: str) -> ScAddr | None:
        if idtf not in self._keynodes:
            addr = ScKeynodes.get(idtf)
            self._keynodes[idtf] = addr if addr is not None and addr.is_valid() else None
        return self._keynodes[idtf]

    def related(self, source: ScAddr, relation: str, *, link: bool = False) -> list[ScAddr]:
        relation_addr = self.keynode(relation)
        if relation_addr is None:
            return []
        target_type = sc_type.VAR_NODE_LINK if link else sc_type.VAR_NODE
        templ = ScTemplate()
        templ.quintuple(
            source,
            sc_type.VAR_COMMON_ARC,
            (target_type, "_target"),
            sc_type.VAR_PERM_POS_ARC,
            relation_addr,
        )
        rows = search_by_template(templ)
        result: list[ScAddr] = []
        for row in rows:
            addr = row.get("_target")
            if addr is not None and addr.is_valid():
                result.append(addr)
        return result

    def link_values(self, node: ScAddr, relation: str) -> list[str]:
        values: list[str] = []
        for link in self.related(node, relation, link=True):
            value = get_link_content_data(link)
            if value is not None and str(value):
                values.append(str(value))
        return values

    def link_value(self, node: ScAddr, relation: str) -> str | None:
        values = self.link_values(node, relation)
        return values[0] if values else None

    def node_by_id(self, idtf: str) -> ScAddr | None:
        relation = self.keynode("nrel_ui_id")
        if relation is not None:
            try:
                groups = search_links_by_contents(idtf)
            except Exception as exc:  # noqa: BLE001 - fall back to system identifier
                logger.debug("Не удалось найти link по содержимому %s: %s", idtf, exc)
                groups = []
            for link in (item for group in groups for item in group):
                templ = ScTemplate()
                templ.quintuple(
                    (sc_type.VAR_NODE, "_node"),
                    sc_type.VAR_COMMON_ARC,
                    link,
                    sc_type.VAR_PERM_POS_ARC,
                    relation,
                )
                rows = search_by_template(templ)
                if rows:
                    addr = rows[0].get("_node")
                    if addr is not None and addr.is_valid():
                        return addr
        addr = ScKeynodes.get(idtf)
        return addr if addr is not None and addr.is_valid() else None

    def id_for(self, node: ScAddr) -> str:
        values = self.link_values(node, "nrel_ui_id")
        if values:
            return values[0]
        idtf = get_element_system_identifier(node)
        return str(idtf) if idtf else ""

    def class_of(self, node: ScAddr) -> str:
        templ = ScTemplate()
        templ.triple((sc_type.VAR_NODE, "_class"), sc_type.VAR_PERM_POS_ARC, node)
        for row in search_by_template(templ):
            idtf = get_element_system_identifier(row.get("_class"))
            if idtf and str(idtf) in COMPONENT_CLASSES:
                return str(idtf)
        return ""

    def properties_of(self, node: ScAddr) -> dict[str, str]:
        templ = ScTemplate()
        templ.quintuple(
            node,
            sc_type.VAR_COMMON_ARC,
            (sc_type.VAR_NODE_LINK, "_value"),
            sc_type.VAR_PERM_POS_ARC,
            (sc_type.VAR_NODE, "_property"),
        )
        result: dict[str, str] = {}
        for row in search_by_template(templ):
            idtf = get_element_system_identifier(row.get("_property"))
            key = str(idtf or "").removeprefix("concept_ui_")
            if key not in PROPERTY_KEYS:
                continue
            value = get_link_content_data(row.get("_value"))
            if value is not None and str(value):
                result[key] = str(value)
        return result

    def targets_of(self, node: ScAddr, relation: str) -> list[str]:
        return [self.id_for(addr) for addr in self.related(node, relation) if self.id_for(addr)]

    def component(self, node: ScAddr) -> ComponentData:
        return ComponentData(
            idtf=self.id_for(node),
            sc_class=self.class_of(node),
            properties=self.properties_of(node),
            inputs=self.targets_of(node, INPUT_REL),
            outputs=self.targets_of(node, OUTPUT_REL),
            children=self.targets_of(node, CONTAINS_REL),
            addr=node,
        )

    def components(self, interface: ScAddr) -> list[ComponentData]:
        nodes = self.related(interface, COMPOSED_REL)
        return [self.component(node) for node in nodes if self.id_for(node)]


def read_interface(
    interface_id: str,
    selected_ids: Iterable[str] = (),
) -> InstanceContext:
    """Читает интерфейс по `nrel_ui_id` (используется direct-http)."""
    reader = _Reader()
    interface = reader.node_by_id(interface_id)
    if interface is None:
        return InstanceContext(mode="whole", interface_id=interface_id)
    return InstanceContext(
        mode="whole",
        interface_id=interface_id,
        components=reader.components(interface),
        selected_ids=set(selected_ids),
        interface_addr=interface,
    )


def read_context(context: ScAddr | None) -> InstanceContext:
    """Читает узел контекста запроса (rrel_3) в sc-memory режиме."""
    if context is None or not context.is_valid():
        return InstanceContext()
    reader = _Reader()
    mode = reader.link_value(context, "nrel_ui_context_mode") or "none"
    if mode not in CONTEXT_MODES:
        mode = "none"
    interfaces = reader.related(context, "nrel_ui_context_interface")
    selected_addrs = reader.related(context, "nrel_ui_context_component")
    interface = interfaces[0] if interfaces else None
    interface_id = reader.id_for(interface) if interface is not None else None
    selected_ids = {
        reader.id_for(addr) for addr in selected_addrs if reader.id_for(addr)
    }
    components = reader.components(interface) if interface is not None else []
    return InstanceContext(
        mode=mode,
        interface_id=interface_id,
        components=components,
        selected_ids=selected_ids,
        interface_addr=interface,
        selected_addrs=selected_addrs,
    )
