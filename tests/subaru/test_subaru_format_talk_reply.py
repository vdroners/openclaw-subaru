"""Tests for Talk reply formatter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "lib"
sys.path.insert(0, str(LIB))

from subaru_format_talk_reply import format_talk_reply  # noqa: E402


def test_format_status_ok():
    fixture = json.loads((ROOT / "tests" / "subaru" / "fixtures" / "status_ok.json").read_text())
    text = format_talk_reply(fixture)
    assert "Odometer" in text or "Fuel" in text or "Wolfram" in text or "Subaru" in text


def test_format_auth_error():
    payload = {
        "ok": False,
        "error_code": "device_not_authenticated",
        "errors": ["Device not registered"],
        "nickname": "Wolfram",
    }
    text = format_talk_reply(payload)
    assert "device_not_authenticated" in text
    assert "subaru-device-register" in text


def test_format_account_locked():
    payload = {"ok": False, "error_code": "account_locked", "errors": ["accountLocked"]}
    text = format_talk_reply(payload)
    assert "account_locked" in text
    assert "30" in text or "locked" in text.lower()


def _summary_payload(stale_seconds, **status):
    vs = {
        "ODOMETER": 58064,
        "DISTANCE_TO_EMPTY_FUEL": 200,
        "VEHICLE_STATE_TYPE": "IGNITION_OFF",
        "DOOR_BOOT_POSITION": "CLOSED",
        "LOCATION_VALID": True,
        "LATITUDE": 45.5455,
        "LONGITUDE": -122.6708,
        "staleness_seconds": stale_seconds,
    }
    vs.update(status)
    return {
        "ok": True,
        "command": "summary",
        "nickname": "Wolfram",
        "data": {
            "summary_text": "ignored when structured status present",
            "vehicle_status": vs,
            "vehicle_health": {"ISTROUBLE": False},
            "meta": {"staleness_seconds": stale_seconds},
        },
    }


def test_format_status_rich_fields(monkeypatch):
    monkeypatch.delenv("SUBARU_TALK_REFRESH_MAX_AGE_S", raising=False)
    text = format_talk_reply(_summary_payload(120))
    assert text.startswith("Wolfram")
    assert "Odometer: 58064 mi" in text
    assert "Range: 200 mi" in text
    assert "Ignition: IGNITION_OFF" in text
    assert "google.com/maps" in text
    assert "Updated 2m ago" in text
    # No fuel percent in this g2 cache, so no Fuel line should be invented.
    assert "Fuel:" not in text
    # Fresh data must NOT carry the cached warning.
    assert "could not refresh" not in text


def test_format_status_stale_warning(monkeypatch):
    monkeypatch.delenv("SUBARU_TALK_REFRESH_MAX_AGE_S", raising=False)
    text = format_talk_reply(_summary_payload(7200))
    assert "cached" in text.lower()
    assert "could not refresh" in text
    # Still reports the data so the operator sees the numbers, flagged as old.
    assert "Odometer: 58064 mi" in text


def test_format_status_includes_open_door(monkeypatch):
    monkeypatch.delenv("SUBARU_TALK_REFRESH_MAX_AGE_S", raising=False)
    text = format_talk_reply(
        _summary_payload(60, DOOR_FRONT_LEFT_POSITION="OPEN")
    )
    assert "Doors:" in text
    assert "FL open" in text


def test_format_status_summary_text_fallback(monkeypatch):
    monkeypatch.delenv("SUBARU_TALK_REFRESH_MAX_AGE_S", raising=False)
    payload = {
        "ok": True,
        "command": "summary",
        "nickname": "Wolfram",
        "data": {"summary_text": "Wolfram\nOdometer: 100 miles"},
    }
    text = format_talk_reply(payload)
    assert "Odometer: 100 miles" in text


def test_format_status_no_telemetry_hint(monkeypatch):
    monkeypatch.delenv("SUBARU_TALK_REFRESH_MAX_AGE_S", raising=False)
    payload = {"ok": True, "command": "status", "nickname": "Wolfram", "data": {}}
    text = format_talk_reply(payload)
    assert "Wolfram" in text
    assert "fetch" in text
