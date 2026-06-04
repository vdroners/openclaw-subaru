"""Tests for odometer/fuel trip logging + weekly digest (subaru_trips)."""

from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "lib"))

from subaru_trips import (  # noqa: E402
    parse_sample,
    append_sample,
    load_samples,
    weekly_digest,
)


def test_parse_sample_extracts_odometer_and_fuel():
    s = parse_sample({"ODOMETER": 12345, "REMAINING_FUEL_PERCENT": 60})
    assert s["odometer"] == 12345.0
    assert s["fuel_percent"] == 60.0


def test_parse_sample_none_without_odometer():
    assert parse_sample({"REMAINING_FUEL_PERCENT": 60}) is None
    assert parse_sample({}) is None


def test_append_dedupes_same_odometer(tmp_path):
    log = tmp_path / "trips.jsonl"
    assert append_sample(log, parse_sample({"ODOMETER": 100})) is True
    # Same odometer is skipped.
    assert append_sample(log, parse_sample({"ODOMETER": 100})) is False
    assert append_sample(log, parse_sample({"ODOMETER": 120})) is True
    assert len(load_samples(log)) == 2


def test_weekly_digest_miles_in_window():
    now = dt.datetime.now(dt.timezone.utc)
    samples = [
        {"ts": (now - dt.timedelta(days=6)).isoformat(), "odometer": 1000},
        {"ts": (now - dt.timedelta(days=3)).isoformat(), "odometer": 1080},
        {"ts": (now - dt.timedelta(days=0)).isoformat(), "odometer": 1142},
    ]
    assert weekly_digest(samples, now=now) == "Driven last 7d: 142 mi"


def test_weekly_digest_none_when_insufficient():
    now = dt.datetime.now(dt.timezone.utc)
    assert weekly_digest([], now=now) is None
    assert weekly_digest([{"ts": now.isoformat(), "odometer": 10}], now=now) is None


def test_weekly_digest_ignores_old_samples():
    now = dt.datetime.now(dt.timezone.utc)
    samples = [
        {"ts": (now - dt.timedelta(days=30)).isoformat(), "odometer": 100},
        {"ts": (now - dt.timedelta(days=1)).isoformat(), "odometer": 900},
    ]
    # Only one sample falls inside the 7-day window -> no digest.
    assert weekly_digest(samples, now=now) is None
