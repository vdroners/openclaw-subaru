"""Unit tests for Subaru health scorecard and related helpers."""

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
    report = evaluate_health({}, {"ISTROUBLE": True}, {})
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
        "DeviceNotAuthenticated": "device_not_authenticated",
        "AccountLocked": "account_locked",
        "SubaruException": "subaru_api",
    }
    for name, code in cases.items():
        exc = type(name, (Exception,), {})()
        assert exception_to_error_code(exc) == code


def test_subarulink_message_codes():
    from subaru_health import subarulink_error_code_from_message

    assert subarulink_error_code_from_message("accountLocked") == "account_locked"
    assert subarulink_error_code_from_message("DEVICE_NOT_AUTHENTICATED") == "device_not_authenticated"


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


def test_fuel_range_fail():
    report = evaluate_health(
        {"DISTANCE_TO_EMPTY_FUEL": 5},
        {"ISTROUBLE": False},
        {},
        {"fuel_range_miles_warn": 30, "fuel_range_miles_fail": 10},
    )
    assert any(c["id"] == "H-FUEL-RNG" and c["status"] == "fail" for c in report["checks"])


def test_tpms_low():
    status = {
        "TYRE_PRESSURE_FRONT_LEFT": 22,
        "TYRE_PRESSURE_FRONT_RIGHT": 32,
        "TYRE_PRESSURE_REAR_LEFT": 32,
        "TYRE_PRESSURE_REAR_RIGHT": 32,
    }
    health = {
        "ISTROUBLE": False,
        "RECOMMENDED_TIRE_PRESSURE": {"FRONT_TIRES": 33, "REAR_TIRES": 33},
    }
    report = evaluate_health(status, health, {"has_tpms": True})
    assert any(c["id"] == "H-TPMS-LOW" for c in report["checks"])


def test_tpms_high():
    status = {
        "TYRE_PRESSURE_FRONT_LEFT": 50,
        "TYRE_PRESSURE_FRONT_RIGHT": 32,
        "TYRE_PRESSURE_REAR_LEFT": 32,
        "TYRE_PRESSURE_REAR_RIGHT": 32,
    }
    health = {
        "ISTROUBLE": False,
        "RECOMMENDED_TIRE_PRESSURE": {"FRONT_TIRES": 33, "REAR_TIRES": 33},
    }
    report = evaluate_health(status, health, {"has_tpms": True})
    assert any(c["id"] == "H-TPMS-HIGH" for c in report["checks"])


def test_stale_data_warn():
    report = evaluate_health(
        {"staleness_seconds": 90000},
        {"ISTROUBLE": False},
        {},
        {"staleness_hours_warn": 24, "staleness_hours_fail": 72},
    )
    assert any(c["id"] == "H-STALE" and c["status"] == "warn" for c in report["checks"])


def test_door_open_warn():
    report = evaluate_health({"DOOR_FRONT_LEFT_POSITION": "OPEN"}, {}, {})
    assert any(c["id"] == "H-DOOR" for c in report["checks"])


def test_lock_unlocked_warn():
    report = evaluate_health({"LOCK_ALL_DOORS_STATUS": "UNLOCKED"}, {}, {})
    assert any(c["id"] == "H-LOCK" for c in report["checks"])


def test_stale_fail():
    report = evaluate_health(
        {"staleness_seconds": 300000},
        {},
        {},
        {"staleness_hours_warn": 24, "staleness_hours_fail": 72},
    )
    assert any(c["id"] == "H-STALE" and c["status"] == "fail" for c in report["checks"])


def test_res_warn():
    report = evaluate_health({}, {}, {"res_status": False})
    assert any(c["id"] == "H-RES" for c in report["checks"])


def test_sub_fail():
    report = evaluate_health({}, {}, {"subscription_status": False})
    assert any(c["id"] == "H-SUB" for c in report["checks"])


def test_ev_soc_warn():
    report = evaluate_health({"EV_STATE_OF_CHARGE_PERCENT": 15}, {}, {"ev": True})
    assert any(c["id"] == "H-EV-SOC" for c in report["checks"])
