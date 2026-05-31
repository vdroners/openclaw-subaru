"""Unit tests for Subaru health scorecard (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "lib"
sys.path.insert(0, str(LIB))

from subaru_health import evaluate_health, exception_to_error_code  # noqa: E402


def test_clean_health_passes():
    report = evaluate_health(
        {"REMAINING_FUEL_PERCENT": 50, "DISTANCE_TO_EMPTY_FUEL": 200, "ODOMETER": 1000},
        {"ISTROUBLE": False},
        {"has_tpms": False, "subscription_status": True, "res_status": True},
    )
    assert report["verdict"] == "pass"
    assert report["score"] >= 90


def test_mil_fails():
    report = evaluate_health(
        {},
        {"ISTROUBLE": True},
        {},
    )
    assert report["verdict"] == "fail"
    assert any(c["id"] == "H-MIL" for c in report["checks"])


def test_exception_mapping():
    class InvalidPIN(Exception):
        pass

    assert exception_to_error_code(InvalidPIN()) == "pin_invalid"
