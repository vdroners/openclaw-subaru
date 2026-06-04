"""Tests for the FastAPI bridge app (auth + routing + maps-link).

Skipped automatically when FastAPI/Starlette test deps are not installed (e.g. a
minimal CI image); the bridge is an optional Phase 2 component.
"""

from __future__ import annotations

import importlib.util
import os
import sys

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # required by starlette TestClient

from fastapi.testclient import TestClient  # noqa: E402

APP_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "services", "subaru-bridge", "app.py"
)
LIB = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "lib")
sys.path.insert(0, LIB)


def _load_app(monkeypatch, api_key=""):
    monkeypatch.setenv("SUBARU_BRIDGE_API_KEY", api_key)
    spec = importlib.util.spec_from_file_location("subaru_bridge_app", APP_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Stub the heavy core call so the test never touches MySubaru.
    mod.run_command = lambda command, args=None: {"ok": True, "command": command, "args": args or {}}
    return mod


def test_health_open_no_auth(monkeypatch):
    mod = _load_app(monkeypatch)
    client = TestClient(mod.app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "subaru-bridge"


def test_maps_link_route_exists(monkeypatch):
    mod = _load_app(monkeypatch)
    client = TestClient(mod.app)
    r = client.get("/maps-link")
    assert r.status_code == 200
    assert r.json()["command"] == "maps-link"


def test_auth_required_when_key_set(monkeypatch):
    mod = _load_app(monkeypatch, api_key="topsecret")
    client = TestClient(mod.app)
    assert client.get("/status").status_code == 401
    assert client.get("/status", headers={"X-API-Key": "wrong"}).status_code == 401
    ok = client.get("/status", headers={"X-API-Key": "topsecret"})
    assert ok.status_code == 200
    assert ok.json()["command"] == "status"


def test_command_passthrough(monkeypatch):
    mod = _load_app(monkeypatch)
    client = TestClient(mod.app)
    r = client.post("/command", json={"command": "lock", "args": {"vin": "V1"}})
    assert r.status_code == 200
    assert r.json()["command"] == "lock"
    assert r.json()["args"] == {"vin": "V1"}
