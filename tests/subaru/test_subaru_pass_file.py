"""Tests for Tier 3 pass file validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from subaru_pass_file import validate_pass_file  # noqa: E402


def test_pass_file_requires_core_gates(tmp_path):
    path = tmp_path / "pass.json"
    path.write_text(json.dumps({"gates": {"SUB-LIVE-LOCK": True}}), encoding="utf-8")
    result = validate_pass_file(path)
    assert result["ok"] is False
    assert "SUB-LIVE-START" in result["missing"]


def test_is_cleared_for_actuation(tmp_path):
    from subaru_pass_file import is_cleared_for_actuation  # noqa: E402

    assert is_cleared_for_actuation(tmp_path / "missing.json")[0] is False
    path = tmp_path / "pass.json"
    path.write_text(
        json.dumps({"passed_at": "2026-01-01T00:00:00Z", "gates": {"SUB-LIVE-LOCK": True}}),
        encoding="utf-8",
    )
    assert is_cleared_for_actuation(path)[0] is True
