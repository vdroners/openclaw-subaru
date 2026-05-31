"""Loopback REST bridge for MySubaru commands (Phase 2)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "lib"
sys.path.insert(0, str(LIB))

from subaru_core import run_command  # noqa: E402

app = FastAPI(title="subaru-bridge", version="1.0.0")
API_KEY = os.environ.get("SUBARU_BRIDGE_API_KEY", "")


def _auth(x_api_key: str | None) -> None:
    if API_KEY and x_api_key != API_KEY:
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


@app.get("/locate")
def locate(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> dict:
    _auth(x_api_key)
    return run_command("locate", {})


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
