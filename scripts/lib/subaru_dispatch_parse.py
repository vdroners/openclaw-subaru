#!/usr/bin/env python3
"""Parse Talk messages into subaru-vehicle CLI actions (JSON stdout)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
from subaru_talk_match import extract_user_message, is_subaru_command  # noqa: E402

KNOWN = frozenset(
    {
        "status",
        "summary",
        "locate",
        "maps",
        "maps-link",
        "condition",
        "capabilities",
        "fetch",
        "presets",
        "lock",
        "unlock",
        "stop",
        "horn",
        "lights",
        "charge",
        "start",
        "health-report",
        "health",
        # Talk-friendly aliases
        "fuel",
        "doors",
        "door",
        "tires",
        "tire",
        "tpms",
    }
)

# Map spoken aliases to CLI commands.
_ACTION_ALIASES = {
    "fuel": "condition",
    "doors": "condition",
    "door": "condition",
    "tires": "health-report",
    "tire": "health-report",
    "tpms": "health-report",
}


def parse_dispatch(
    message: str,
    agent_name: str = "openclaw",
    vehicle_aliases: dict[str, str] | None = None,
) -> dict | None:
    if not is_subaru_command(message, agent_name):
        return None
    norm = extract_user_message(message)
    agent = agent_name.lstrip("@")
    # Drop optional "@<agent>" prefix and the word "subaru" (anywhere for NL: "is subaru locked").
    rest = re.sub(rf"(?i)^@?{re.escape(agent)}\s+", "", norm)
    rest = re.sub(r"(?i)\bsubaru\b", " ", rest)
    rest = re.sub(r"\s+", " ", rest).strip()
    if not rest:
        return {"action": "status", "args": []}
    parts = rest.split()
    # Multi-vehicle: an optional leading nickname (e.g. "subaru outback status")
    # is consumed when it maps to a configured VIN and is not itself a subcommand.
    selected_vin = ""
    aliases = {str(k).lower(): str(v) for k, v in (vehicle_aliases or {}).items()}
    if parts and parts[0].lower() in aliases and parts[0].lower() not in KNOWN:
        selected_vin = aliases[parts[0].lower()]
        parts = parts[1:]
    if not parts:
        return {"action": "status", "args": (["--vin", selected_vin] if selected_vin else [])}
    # Strip optional trailing confirm token (Talk actuation safety).
    if parts and parts[-1].lower() == "confirm":
        parts = parts[:-1]
    if not parts:
        return {"action": "status", "args": (["--vin", selected_vin] if selected_vin else [])}
    sub = parts[0].lower()
    arg2 = parts[1] if len(parts) > 1 else ""
    arg3 = parts[2] if len(parts) > 2 else ""
    # NL: "is … locked/unlocked", "where is the car" (locate), "door status"
    if sub not in KNOWN and sub not in _ACTION_ALIASES and sub not in ("maps", "health", "health-report"):
        joined = " ".join(parts).lower()
        if re.search(r"\b(unlock|unlocked)\b", joined):
            sub, arg2, arg3 = "unlock", "", ""
        elif re.search(r"\b(lock|locked)\b", joined):
            sub, arg2, arg3 = "lock", "", ""
        elif re.search(r"\b(where|locate|location|parked)\b", joined):
            sub, arg2, arg3 = "locate", "", ""
        elif re.search(r"\b(fuel|gas|range)\b", joined):
            sub, arg2, arg3 = "fuel", "", ""
        elif re.search(r"\b(door|doors)\b", joined):
            sub, arg2, arg3 = "doors", "", ""
        elif re.search(r"\b(tire|tires|tpms)\b", joined):
            sub, arg2, arg3 = "tires", "", ""
        elif re.search(r"\b(status|summary|how.?s it)\b", joined):
            sub, arg2, arg3 = "status", "", ""
        else:
            # First known verb anywhere in the remaining tokens
            found = next((p.lower() for p in parts if p.lower() in KNOWN or p.lower() in _ACTION_ALIASES), "")
            if not found:
                return None
            sub = found
            arg2 = arg3 = ""
    if sub == "maps":
        action = "maps-link"
    elif sub in ("health", "health-report"):
        action = "health-report"
    elif sub in _ACTION_ALIASES:
        action = _ACTION_ALIASES[sub]
    elif sub in KNOWN:
        action = sub
    else:
        return None
    args: list[str] = []
    if action == "start" and arg2:
        args = ["--preset", arg2]
    elif action == "unlock" and arg2 in ("driver", "drivers", "tailgate", "all"):
        args = ["--door", arg2]
    elif action == "unlock" and arg2 and arg3:
        args = ["--door", arg3]
    if selected_vin:
        args = ["--vin", selected_vin] + args
    return {"action": action, "args": args}


def _load_aliases(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    return {}


def main() -> int:
    import os

    msg = sys.argv[1] if len(sys.argv) > 1 else ""
    agent = sys.argv[2] if len(sys.argv) > 2 else "openclaw"
    aliases = _load_aliases(os.environ.get("SUBARU_VEHICLE_ALIASES"))
    parsed = parse_dispatch(msg, agent, aliases)
    if not parsed:
        return 1
    print(json.dumps(parsed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
