"""T8: метрика неизвестных id учитывает каталог и экземпляр раздельно."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _load_eval() -> ModuleType:
    spec = importlib.util.spec_from_file_location("t8_run_eval", ROOT / "tools" / "run_eval.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _item(
    item_id: str, *, catalog: list[str] | None = None, instance: list[str] | None = None
) -> dict[str, Any]:
    catalog = catalog or []
    instance = instance or []
    return {
        "id": item_id,
        "category": "compare",
        "question": "",
        "answer": "",
        "passed": True,
        "missing": [],
        "forbidden": [],
        "missing_any": [],
        "latency_ms": 1.0,
        "wall_ms": 1.0,
        "prompt_tokens": 1,
        "output_tokens": 1,
        "token_budget_warning": False,
        "hallucinated": False,
        "unknown_in_final": [*catalog, *instance],
        "unknown_in_final_catalog": catalog,
        "unknown_in_final_instance": instance,
        "validation_removed": [],
        "sources": [],
        "guard": "",
        "injection": False,
    }


def test_eval_reports_unknown_ids_by_class() -> None:
    run_eval = _load_eval()
    summary = run_eval.summarize(
        [
            _item("a", catalog=["ui_fake_section"]),
            _item("b", instance=["cmp_999"]),
            _item("c"),
        ],
        None,
    )

    assert summary["unknown_id_in_final_rate"] == 0.6667
    assert summary["unknown_catalog_in_final_rate"] == 0.3333
    assert summary["unknown_instance_in_final_rate"] == 0.3333
    assert summary["unknown_catalog_final"] == 1
    assert summary["unknown_instance_final"] == 1
    assert run_eval.THRESHOLDS["unknown_id_in_final_rate"] == 0.0
