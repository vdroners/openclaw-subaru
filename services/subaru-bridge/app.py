"""Loopback REST bridge for MySubaru commands (Phase 2)."""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# Resolve the lib dir robustly: prefer an explicit PYTHONPATH-style override, then
# the repo-relative layout (host checkout), then the container layout (/app/scripts/lib).
_HERE = Path(__file__).resolve()
_CANDIDATES = [
    _HERE.parents[2] / "scripts" / "lib",   # repo checkout: services/subaru-bridge/app.py
    _HERE.parent / "scripts" / "lib",       # container: /app/app.py + /app/scripts/lib
]
for _lib in _CANDIDATES:
    if _lib.is_dir():
        sys.path.insert(0, str(_lib))
        break

from subaru_core import run_command  # noqa: E402

app = FastAPI(title="subaru-bridge", version="1.0.0")
API_KEY = os.environ.get("SUBARU_BRIDGE_API_KEY", "")


def _auth(x_api_key: str | None) -> None:
    if API_KEY and not secrets.compare_digest(str(x_api_key or ""), API_KEY):
        raise HTTPException(status_code=401, detail="unauthorized")


class CommandBody(BaseModel):
    command: str
    args: dict | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "subaru-bridge"}


@app.get("/capabilities")
def capabilities(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command("capabilities", {})


@app.get("/status")
def status(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command("status", {})


@app.get("/summary")
def summary(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command("summary", {})


@app.get("/health-report")
def health_report(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command("health-report", {"prefetch": True})


@app.get("/condition")
def condition(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command("condition", {})


@app.get("/locate")
def locate(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command("locate", {})


@app.get("/maps-link")
def maps_link(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command("maps-link", {})


@app.get("/presets")
def presets(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command("presets-list", {})


@app.post("/fetch")
def fetch(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command("fetch", {})


@app.post("/update")
def update(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command("update", {})


@app.post("/command")
def command(body: CommandBody, x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command(body.command, body.args or {})
