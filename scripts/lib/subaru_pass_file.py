"""Validate Tier 3 actuation pass file gate booleans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_GATES = (
    "SUB-LIVE-LOCK",
    "SUB-LIVE-UNLOCK",
    "SUB-LIVE-START",
    "SUB-LIVE-STOP",
)
OPTIONAL_GATES = (
    "SUB-LIVE-UNLOCK-DRIVER",
    "SUB-LIVE-HORN",
    "SUB-LIVE-LIGHTS",
    "SUB-LIVE-CHARGE",
)


def validate_pass_file(path: str | Path, *, require_ev_charge: bool = False) -> dict[str, Any]:
    """Return {ok, missing, warnings, gates}."""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "missing": list(REQUIRED_GATES), "warnings": [], "gates": {}}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"ok": False, "missing": list(REQUIRED_GATES), "warnings": ["invalid json"], "gates": {}}
    gates = payload.get("gates") or {}
    missing = [g for g in REQUIRED_GATES if not gates.get(g)]
    if require_ev_charge and not gates.get("SUB-LIVE-CHARGE"):
        missing.append("SUB-LIVE-CHARGE")
    warnings: list[str] = []
    for g in OPTIONAL_GATES:
        if g in gates and not gates.get(g):
            warnings.append(f"{g} skipped")
    return {
        "ok": len(missing) == 0,
        "missing": missing,
        "warnings": warnings,
        "gates": gates,
    }
