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
        "update",
        "refresh",
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

# Subaru cloud climate presets that every account has. Account-specific presets
# (e.g. a custom "Dan Da Dan") come from the vehicle JSON ``remote_start_preset``,
# an optional vehicle JSON ``preset_names`` list, or SUBARU_PRESET_NAMES (comma list).
BUILTIN_PRESETS = ("Auto", "Full Cool", "Full Heat")

_QUOTE_CHARS = "\"'\u201c\u201d\u2018\u2019`"
# Filler words between "start" and the preset name: "start with Dan Da Dan",
# "start using preset Full Heat", "start on full heat".
_PRESET_FILLER_RE = re.compile(
    r"(?i)^(?:(?:up|it|the|car|engine|vehicle|subaru|wolfram|outback|now|with|using|use|on|in|"
    r"preset|climate|mode|setting)\b\s*)+"
)
_PRESET_TRAILER_RE = re.compile(r"(?i)(?:\s*\b(?:please|now|thanks|thank you|preset)\b)+[.!?]*$")

# Map spoken aliases to CLI commands.
_ACTION_ALIASES = {
    # Explicit "get a fresh reading from the car" (wakes the car; core throttles
    # it with SUBARU_UPDATE_MIN_INTERVAL_S).
    "refresh": "update",
    "fuel": "condition",
    "doors": "condition",
    "door": "condition",
    "tires": "health-report",
    "tire": "health-report",
    "tpms": "health-report",
}


def known_preset_names(extra: list[str] | None = None) -> list[str]:
    """Preset names we can canonicalise against (case-insensitive)."""
    import os

    names: list[str] = list(BUILTIN_PRESETS)
    raw_env = os.environ.get("SUBARU_PRESET_NAMES", "")
    names.extend(n.strip() for n in raw_env.split(",") if n.strip())
    vj = os.environ.get("SUBARU_VEHICLE_JSON", "")
    if vj:
        try:
            cfg = json.loads(Path(vj).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            cfg = {}
        if isinstance(cfg, dict):
            default = str(cfg.get("remote_start_preset") or "").strip()
            if default:
                names.append(default)
            extra_cfg = cfg.get("preset_names")
            if isinstance(extra_cfg, list):
                names.extend(str(n).strip() for n in extra_cfg if str(n).strip())
    names.extend(extra or [])
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


def parse_preset(tokens: list[str], known: list[str] | None = None) -> str:
    """Join every remaining token into one preset name.

    ``["Dan", "Da", "Dan"]`` -> ``"Dan Da Dan"``; quotes (straight or curly) are
    stripped; filler like "with"/"preset" is dropped; a case-insensitive match
    against known presets returns the canonical spelling. Unknown names are
    passed through unchanged so the CLI can report ``preset_missing``.
    """
    raw = " ".join(tokens).strip()
    raw = raw.strip(_QUOTE_CHARS).strip()
    raw = _PRESET_FILLER_RE.sub("", raw).strip()
    raw = _PRESET_TRAILER_RE.sub("", raw).strip()
    raw = raw.strip(_QUOTE_CHARS + ".!?,").strip()
    raw = re.sub(r"\s+", " ", raw)
    if not raw:
        return ""
    names = known if known is not None else known_preset_names()
    for name in names:
        if name.lower() == raw.lower():
            return name
    return raw


def parse_dispatch(
    message: str,
    agent_name: str = "openclaw",
    vehicle_aliases: dict[str, str] | None = None,
    known_presets: list[str] | None = None,
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
    preset_tokens = parts[1:] if sub in ("start", "remote_start") else []
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
            preset_tokens = []
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
    if action == "start" and preset_tokens:
        preset = parse_preset(preset_tokens, known_presets)
        if preset:
            args = ["--preset", preset]
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
