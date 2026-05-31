"""HTTP client for subaru-bridge (Phase 2)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


READ_ROUTES = {
    "status": ("GET", "/status"),
    "summary": ("GET", "/summary"),
    "capabilities": ("GET", "/capabilities"),
    "condition": ("GET", "/condition"),
    "health-report": ("GET", "/health-report"),
    "locate": ("GET", "/locate"),
    "maps-link": ("GET", "/status"),
    "presets-list": ("GET", "/presets"),
    "fetch": ("POST", "/fetch"),
    "update": ("POST", "/update"),
}

ACTUATION_COMMANDS = frozenset(
    {"lock", "unlock", "start", "stop", "horn", "lights", "charge", "remote_start", "remote_stop"}
)


def load_api_key() -> str:
    key = os.environ.get("SUBARU_BRIDGE_API_KEY", "").strip()
    if key:
        return key
    key_file = os.environ.get("SUBARU_BRIDGE_KEY_FILE", "").strip()
    if key_file:
        path = os.path.expanduser(key_file)
        if os.path.isfile(path):
            return open(path, encoding="utf-8").read().strip()
    return ""


def map_command_to_http(command: str, args: dict[str, Any] | None) -> tuple[str, str, dict[str, Any] | None]:
    args = args or {}
    cmd = command
    if cmd == "remote_start":
        cmd = "start"
    elif cmd == "remote_stop":
        cmd = "stop"
    if cmd in READ_ROUTES:
        method, path = READ_ROUTES[cmd]
        return method, path, None
    if cmd in ACTUATION_COMMANDS or cmd.startswith("presets-") or cmd.startswith("auth-") or cmd == "pin-test":
        body = {"command": command, "args": args}
        return "POST", "/command", body
    if cmd in READ_ROUTES:
        method, path = READ_ROUTES[cmd]
        return method, path, None
    return "POST", "/command", {"command": command, "args": args}


def run_bridge_command(
    base_url: str,
    command: str,
    args: dict[str, Any] | None = None,
    *,
    api_key: str | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    base = base_url.rstrip("/")
    api_key = api_key if api_key is not None else load_api_key()
    method, path, body = map_command_to_http(command, args)
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{base}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {"ok": False, "errors": [str(exc)], "error_code": "bridge_http"}
        return payload
    except urllib.error.URLError as exc:
        return {"ok": False, "command": command, "errors": [str(exc)], "error_code": "bridge_unreachable"}
