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
    }
)


def parse_dispatch(message: str, agent_name: str = "openclaw") -> dict | None:
    if not is_subaru_command(message, agent_name):
        return None
    norm = extract_user_message(message)
    agent = agent_name.lstrip("@")
    # Drop optional "@<agent>" prefix and the word "subaru".
    rest = re.sub(rf"(?i)^@?{re.escape(agent)}\s+", "", norm)
    rest = re.sub(r"(?i)^subaru\s*", "", rest).strip()
    if not rest:
        return {"action": "status", "args": []}
    parts = rest.split()
    sub = parts[0].lower()
    arg2 = parts[1] if len(parts) > 1 else ""
    arg3 = parts[2] if len(parts) > 2 else ""
    if sub == "maps":
        action = "maps-link"
    elif sub in ("health", "health-report"):
        action = "health-report"
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
    return {"action": action, "args": args}


def main() -> int:
    msg = sys.argv[1] if len(sys.argv) > 1 else ""
    agent = sys.argv[2] if len(sys.argv) > 2 else "openclaw"
    parsed = parse_dispatch(msg, agent)
    if not parsed:
        return 1
    print(json.dumps(parsed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
