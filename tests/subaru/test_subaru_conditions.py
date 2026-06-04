"""Tests for proactive condition-transition detection (subaru_conditions)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "lib"))

from subaru_conditions import (  # noqa: E402
    condition_signature,
    new_conditions,
    cleared_conditions,
    messages_for,
    should_post_conditions,
)


def _checks(*items):
    return [{"id": i, "status": s, "message": m} for i, s, m in items]


def test_signature_keeps_actionable_warns_drops_stale():
    checks = _checks(
        ("H-DOOR", "warn", "DOOR_FRONT_LEFT_POSITION is OPEN"),
        ("H-STALE", "warn", "Data stale 30h"),
        ("H-OK", "pass", "No issues detected"),
    )
    sig = condition_signature(checks)
    assert sig == ["H-DOOR|DOOR_FRONT_LEFT_POSITION is OPEN"]


def test_new_condition_posts_then_dedupes():
    sig = condition_signature(_checks(("H-FUEL-PCT", "warn", "Fuel 12%")))
    post, msgs, reason = should_post_conditions([], sig)
    assert post is True
    assert msgs == ["Fuel 12%"]
    assert reason == "condition_change"
    # Same condition next run is suppressed.
    post2, _, reason2 = should_post_conditions(sig, sig)
    assert post2 is False
    assert reason2 == "no_new_conditions"


def test_second_condition_at_same_rank_still_posts():
    prev = condition_signature(_checks(("H-FUEL-PCT", "warn", "Fuel 12%")))
    cur = condition_signature(
        _checks(
            ("H-FUEL-PCT", "warn", "Fuel 12%"),
            ("H-DOOR", "warn", "DOOR_BOOT_POSITION is OPEN"),
        )
    )
    post, msgs, _ = should_post_conditions(prev, cur)
    assert post is True
    assert msgs == ["DOOR_BOOT_POSITION is OPEN"]


def test_cleared_conditions_tracked():
    prev = condition_signature(_checks(("H-DOOR", "warn", "DOOR_BOOT_POSITION is OPEN")))
    cur = condition_signature(_checks(("H-OK", "pass", "ok")))
    assert cleared_conditions(prev, cur) == prev
    assert new_conditions(prev, cur) == []


def test_messages_for_handles_plain_strings():
    assert messages_for(["H-DOOR|boot open"]) == ["boot open"]
    assert messages_for(["legacy"]) == ["legacy"]
