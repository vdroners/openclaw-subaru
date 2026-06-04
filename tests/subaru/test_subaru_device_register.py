"""Offline arg-plumbing tests for subaru_device_register (no network)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "lib"))

import subaru_device_register as reg  # noqa: E402


def _capture(monkeypatch):
    captured = {}

    async def fake_register(code, *, request_first):
        captured["code"] = code
        captured["request_first"] = request_first
        return 0

    monkeypatch.setattr(reg, "_register", fake_register)
    return captured


def test_code_from_positional_arg(monkeypatch):
    captured = _capture(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["subaru-device-register", "123456"])
    assert reg.main() == 0
    assert captured == {"code": "123456", "request_first": False}


def test_request_flag_and_env_code(monkeypatch):
    captured = _capture(monkeypatch)
    monkeypatch.setenv("SUBARU_DEVICE_REGISTER_CODE", "654321")
    monkeypatch.setattr(sys, "argv", ["subaru-device-register", "--request"])
    assert reg.main() == 0
    assert captured["code"] == "654321"
    assert captured["request_first"] is True


def test_empty_code_defaults_blank(monkeypatch):
    captured = _capture(monkeypatch)
    monkeypatch.delenv("SUBARU_DEVICE_REGISTER_CODE", raising=False)
    monkeypatch.setattr(sys, "argv", ["subaru-device-register"])
    assert reg.main() == 0
    assert captured["code"] == ""
