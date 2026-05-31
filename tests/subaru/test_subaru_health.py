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


def test_exception_mapping_matrix():
    cases = {
        "InvalidCredentials": "auth_invalid",
        "IncompleteCredentials": "auth_incomplete",
        "InvalidPIN": "pin_invalid",
        "PINLockoutProtect": "pin_lockout",
        "VehicleNotSupported": "unsupported",
        "RemoteServiceFailure": "remote_failed",
        "SubaruException": "subaru_api",
    }
    for name, code in cases.items():
        exc = type(name, (Exception,), {})()
        assert exception_to_error_code(exc) == code


def test_fuel_low_warn():
    report = evaluate_health(
        {"REMAINING_FUEL_PERCENT": 12, "DISTANCE_TO_EMPTY_FUEL": 50},
        {"ISTROUBLE": False},
        {},
        {"fuel_percent_warn": 15, "fuel_percent_fail": 5},
    )
    assert any(c["id"] == "H-FUEL-PCT" and c["status"] == "warn" for c in report["checks"])


def test_fuel_low_fail():
    report = evaluate_health(
        {"REMAINING_FUEL_PERCENT": 3, "DISTANCE_TO_EMPTY_FUEL": 8},
        {"ISTROUBLE": False},
        {},
        {"fuel_percent_warn": 15, "fuel_percent_fail": 5, "fuel_range_miles_fail": 10},
    )
    assert report["verdict"] == "fail"
    assert any(c["id"] == "H-FUEL-PCT" and c["status"] == "fail" for c in report["checks"])


def test_tpms_low():
    status = {
        "TIRE_PRESSURE_FL": 22,
        "TIRE_PRESSURE_FR": 32,
        "TIRE_PRESSURE_RL": 32,
        "TIRE_PRESSURE_RR": 32,
        "TIRE_PRESSURE_RECOMMENDED_FRONT": 33,
        "TIRE_PRESSURE_RECOMMENDED_REAR": 33,
    }
    report = evaluate_health(status, {"ISTROUBLE": False}, {"has_tpms": True})
    assert any(c["id"] == "H-TPMS-LOW" for c in report["checks"])


def test_stale_data_warn():
    report = evaluate_health(
        {"staleness_seconds": 90000},
        {"ISTROUBLE": False},
        {},
        {"staleness_hours_warn": 24, "staleness_hours_fail": 72},
    )
    assert any(c["id"] == "H-STALE" and c["status"] == "warn" for c in report["checks"])
