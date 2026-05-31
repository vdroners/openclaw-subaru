"""Tests for bridge HTTP client routing."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

from subaru_bridge_client import map_command_to_http  # noqa: E402


def test_map_status_get():
    method, path, body = map_command_to_http("status", {})
    assert method == "GET"
    assert path == "/status"
    assert body is None


def test_map_lock_post_command():
    method, path, body = map_command_to_http("lock", {})
    assert method == "POST"
    assert path == "/command"
    assert body["command"] == "lock"


def test_map_health_report_get():
    method, path, _ = map_command_to_http("health-report", {"prefetch": True})
    assert method == "GET"
    assert path == "/health-report"
