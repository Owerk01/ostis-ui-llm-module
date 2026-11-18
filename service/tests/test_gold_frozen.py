"""Заморозка выборок и шаблона промпта."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_gold_frozen_hashes() -> None:
    frozen = json.loads((ROOT / "eval" / "frozen.json").read_text(encoding="utf-8"))
    for name in ("gold_questions.jsonl", "holdout_questions.jsonl", "prompt_v4.md"):
        path = ROOT / "eval" / name if name.endswith(".jsonl") else ROOT / "knowledge" / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert frozen[name] == digest, f"хэш {name} изменился после заморозки"
