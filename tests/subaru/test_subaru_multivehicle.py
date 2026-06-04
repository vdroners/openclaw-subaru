"""Tests for multi-vehicle support: dispatch alias + bridge VIN routing."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "lib"))

from subaru_dispatch_parse import parse_dispatch  # noqa: E402
from subaru_bridge_client import map_command_to_http  # noqa: E402

ALIASES = {"outback": "4S4BRCKC8N3400001", "solterra": "JTMAB3FV0N3000002"}


def test_alias_selects_vin_before_action():
    out = parse_dispatch("@openclaw subaru outback status", "openclaw", ALIASES)
    assert out == {"action": "status", "args": ["--vin", "4S4BRCKC8N3400001"]}


def test_alias_with_no_action_defaults_status():
    out = parse_dispatch("@openclaw subaru solterra", "openclaw", ALIASES)
    assert out == {"action": "status", "args": ["--vin", "JTMAB3FV0N3000002"]}


def test_alias_then_start_preset():
    out = parse_dispatch("@openclaw subaru outback start Winter", "openclaw", ALIASES)
    assert out["action"] == "start"
    assert out["args"] == ["--vin", "4S4BRCKC8N3400001", "--preset", "Winter"]


def test_unknown_token_is_not_treated_as_alias():
    # A subcommand keyword is never consumed as a vehicle alias.
    out = parse_dispatch("@openclaw subaru status", "openclaw", ALIASES)
    assert out == {"action": "status", "args": []}


def test_no_aliases_unchanged():
    out = parse_dispatch("@openclaw subaru status", "openclaw")
    assert out == {"action": "status", "args": []}


def test_bridge_vin_routes_read_through_command():
    method, path, body = map_command_to_http("status", {"vin": "VIN123"})
    assert (method, path) == ("POST", "/command")
    assert body == {"command": "status", "args": {"vin": "VIN123"}}


def test_bridge_read_without_vin_uses_get_route():
    method, path, body = map_command_to_http("status", {})
    assert (method, path) == ("GET", "/status")
    assert body is None


def test_bridge_maps_link_not_status():
    method, path, _ = map_command_to_http("maps-link", {})
    assert (method, path) == ("GET", "/maps-link")
