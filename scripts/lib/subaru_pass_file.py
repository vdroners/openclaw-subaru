"""Tier-3 actuation pass-file helpers (offline, no network)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def default_pass_path(openclaw_dir: str | None = None) -> Path:
    base = Path(openclaw_dir or os.environ.get("OPENCLAW_DIR", Path.home() / ".openclaw"))
    return base / "state" / "subaru-gates-live-pass.json"


REQUIRED_GATES = (
    "SUB-LIVE-LOCK",
    "SUB-LIVE-UNLOCK",
    "SUB-LIVE-START",
    "SUB-LIVE-STOP",
)
EV_GATE = "SUB-LIVE-CHARGE"


def validate_pass_file(
    path: str | Path,
    *,
    require_ev_charge: bool = False,
) -> dict[str, Any]:
    """Validate Tier-3 checklist file (used by subaru-gates.sh)."""
    data = load_pass_file(path)
    if not data:
        return {"ok": False, "missing": list(REQUIRED_GATES)}
    gates = data.get("gates") or {}
    if not isinstance(gates, dict):
        return {"ok": False, "missing": list(REQUIRED_GATES)}
    required = list(REQUIRED_GATES)
    if require_ev_charge:
        required.append(EV_GATE)
    missing = [g for g in required if not gates.get(g)]
    return {"ok": len(missing) == 0, "missing": missing}


def load_pass_file(path: str | Path | None = None) -> dict[str, Any] | None:
    p = Path(path) if path else default_pass_path()
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def is_cleared_for_actuation(
    path: str | Path | None = None,
    *,
    max_age_days: float | None = None,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Return (cleared, reason)."""
    data = load_pass_file(path)
    if not data:
        return False, "missing_pass_file"
    passed_at = data.get("passed_at")
    if not passed_at:
        return False, "missing_passed_at"
    try:
        ts = datetime.fromisoformat(str(passed_at).replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return False, "invalid_passed_at"
    if max_age_days is None:
        try:
            max_age_days = float(os.environ.get("SUBARU_ACTUATION_PASS_MAX_AGE_DAYS", "365"))
        except ValueError:
            max_age_days = 365.0
    if max_age_days > 0:
        now = now or datetime.now(timezone.utc)
        age = (now - ts).total_seconds() / 86400.0
        if age > max_age_days:
            return False, f"pass_file_expired_{age:.0f}d"
    gates = data.get("gates") or {}
    if isinstance(gates, dict) and not any(v is True for v in gates.values()):
        return False, "no_gates_passed"
    return True, "ok"
