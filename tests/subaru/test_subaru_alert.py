"""Tests for alert dedup logic."""

from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from subaru_alert import should_post_alert  # noqa: E402


def test_dedup_blocks_recent_post():
    now = datetime.now(timezone.utc)
    state = {"last_post_ts": (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    ok, reason = should_post_alert(
        state,
        verdict="warn",
        score=80,
        prev_verdict="warn",
        prev_score=82,
        min_interval_h=6,
        now=now,
    )
    assert ok is False
    assert reason.startswith("dedup")


def test_dedup_allows_escalation():
    now = datetime.now(timezone.utc)
    state = {"last_post_ts": (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    ok, _ = should_post_alert(
        state,
        verdict="fail",
        score=50,
        prev_verdict="warn",
        prev_score=70,
        min_interval_h=6,
        now=now,
    )
    assert ok is True
