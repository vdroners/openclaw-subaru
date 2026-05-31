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
