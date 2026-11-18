"""sc-модуль ассистента."""

from __future__ import annotations

from sc_kpm import ScModule

from ..knowledge.service import KnowledgeService
from .dialog_agent import UiDialogAgent


class UiDialogModule(ScModule):
    def __init__(self, service: KnowledgeService) -> None:
        super().__init__(UiDialogAgent(service))
