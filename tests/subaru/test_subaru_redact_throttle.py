"""Tests for raw redaction and the global update/fetch throttle."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "lib"))

import subaru_core  # noqa: E402
from subaru_core import _redact_raw, REDACTED, Settings, SubaruRunner  # noqa: E402


def test_redact_raw_masks_sensitive_keys_at_all_depths():
    raw = {
        "vehicle_status": {"ODOMETER": 123},
        "session": {"accessToken": "abc", "refreshToken": "def"},
        "authToken": "secret",
        "nested": [{"password": "p"}, {"pin": "1234"}, {"safe": "ok"}],
    }
    out = _redact_raw(raw)
    assert out["session"] == REDACTED  # key 'session' matched
    assert out["authToken"] == REDACTED
    assert out["nested"][0]["password"] == REDACTED
    assert out["nested"][1]["pin"] == REDACTED
    assert out["nested"][2]["safe"] == "ok"
    assert out["vehicle_status"]["ODOMETER"] == 123
    # No secret value should survive anywhere in the serialized payload.
    text = json.dumps(out)
    assert "abc" not in text and "secret" not in text and "1234" not in text


def _settings(tmp_path, interval, **env):
    base = {
        "OPENCLAW_DIR": str(tmp_path),
        "SUBARU_UPDATE_MIN_INTERVAL_S": str(interval),
    }
    base.update(env)
    for k, v in base.items():
        os.environ[k] = v
    try:
        return Settings(dry_run=False)
    finally:
        for k in base:
            os.environ.pop(k, None)


def test_update_throttle_skips_recent_attempt(tmp_path):
    settings = _settings(tmp_path, 600)
    runner = SubaruRunner(settings)
    settings.update_state.parent.mkdir(parents=True, exist_ok=True)
    settings.update_state.write_text(
        json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()}), encoding="utf-8"
    )
    assert runner._update_throttled() is True
    # force always bypasses
    assert runner._update_throttled(force=True) is False


def test_update_throttle_allows_after_window(tmp_path):
    settings = _settings(tmp_path, 600)
    runner = SubaruRunner(settings)
    settings.update_state.parent.mkdir(parents=True, exist_ok=True)
    old = (datetime.now(timezone.utc) - timedelta(seconds=1200)).isoformat()
    settings.update_state.write_text(json.dumps({"timestamp": old}), encoding="utf-8")
    assert runner._update_throttled() is False


def test_update_throttle_disabled_by_default(tmp_path):
    settings = _settings(tmp_path, 0)
    runner = SubaruRunner(settings)
    assert runner._update_throttled() is False


def test_record_update_attempt_writes_state(tmp_path):
    settings = _settings(tmp_path, 600)
    runner = SubaruRunner(settings)
    runner._record_update_attempt()
    assert settings.update_state.is_file()
    payload = json.loads(settings.update_state.read_text(encoding="utf-8"))
    assert "timestamp" in payload
