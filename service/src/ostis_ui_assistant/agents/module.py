"""sc-модуль ассистента."""

from __future__ import annotations

from sc_kpm import ScModule

from ..knowledge.service import KnowledgeService
from .dialog_agent import UiDialogAgent
from .worker import DialogWorker


class UiDialogModule(ScModule):
    def __init__(self, service: KnowledgeService, worker: DialogWorker) -> None:
        super().__init__(UiDialogAgent(service, worker))
