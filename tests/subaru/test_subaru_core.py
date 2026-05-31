"""Unit tests for Subaru core rate limiting and dry-run envelopes."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "lib"
sys.path.insert(0, str(LIB))

from subaru_core import Settings, SubaruRunner, run_command, validate_response_envelope  # noqa: E402


def test_locate_rate_limited(tmp_path, monkeypatch):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_file = state_dir / "subaru-locate-last.json"
    recent = datetime.now(timezone.utc) - timedelta(minutes=30)
    state_file.write_text(json.dumps({"timestamp": recent.isoformat(), "lat": 1.0, "lon": 2.0}))

    settings = Settings(dry_run=False)
    settings.openclaw_dir = tmp_path
    settings.locate_state = state_file
    settings.locate_min_hours = 2.0
    settings.enabled = True

    runner = SubaruRunner(settings)
    with pytest.raises(RuntimeError, match="rate_limited"):
        runner._check_locate_rate(force=False)


def test_locate_rate_allows_after_interval(tmp_path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_file = state_dir / "subaru-locate-last.json"
    old = datetime.now(timezone.utc) - timedelta(hours=5)
    state_file.write_text(json.dumps({"timestamp": old.isoformat(), "lat": 1.0, "lon": 2.0}))

    settings = Settings(dry_run=False)
    settings.openclaw_dir = tmp_path
    settings.locate_state = state_file
    settings.locate_min_hours = 2.0

    runner = SubaruRunner(settings)
    runner._check_locate_rate(force=False)


def test_dry_run_envelope_required_keys():
    payload = run_command("status", {}, dry_run=True)
    missing = validate_response_envelope(payload)
    assert missing == []
    assert payload["ok"] is True
    assert payload["command"] == "status"


def test_actuation_disabled_lock():
    payload = run_command("lock", {}, dry_run=True)
    assert payload.get("error_code") == "actuation_disabled"


def test_auth_connect_dry():
    payload = run_command("auth-connect", {}, dry_run=True)
    assert payload.get("ok") is True


def test_dry_run_all_read_commands():
    commands = [
        "status",
        "summary",
        "raw",
        "show",
        "fetch",
        "update",
        "locate",
        "capabilities",
        "health",
        "condition",
        "health-report",
        "maps-link",
        "presets-list",
        "presets-show",
        "vehicles-list",
        "auth-check",
        "pin-test",
        "charge",
        "auth-connect",
        "presets-get",
        "vehicles-select",
        "config-set",
    ]
    for cmd in commands:
        payload = run_command(cmd, {}, dry_run=True)
        assert validate_response_envelope(payload) == [], cmd
        assert "ok" in payload
