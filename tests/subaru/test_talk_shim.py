"""Tests for the Talk webhook shim (loopback bind default + actor filtering)."""

from __future__ import annotations

import importlib.util
import os

SHIM_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "talk-webhook-shim.py"
)


def _load_shim():
    spec = importlib.util.spec_from_file_location("talk_webhook_shim", SHIM_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_resolve_listen_host_defaults_loopback():
    shim = _load_shim()
    assert shim.resolve_listen_host({}) == "127.0.0.1"


def test_resolve_listen_host_lan_opt_in():
    shim = _load_shim()
    assert shim.resolve_listen_host({"TALK_SHIM_LAN": "1"}) == "0.0.0.0"


def test_resolve_listen_host_explicit_wins():
    shim = _load_shim()
    assert shim.resolve_listen_host({"TALK_SHIM_HOST": "10.0.0.5", "TALK_SHIM_LAN": "1"}) == "10.0.0.5"


def test_is_openclaw_actor_matches_agent():
    shim = _load_shim()
    assert shim._is_openclaw_actor("users/openclaw", "OpenClaw") is True
    assert shim._is_openclaw_actor("users/dad", "Dad") is False
