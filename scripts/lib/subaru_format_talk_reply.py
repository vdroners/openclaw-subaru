#!/usr/bin/env python3
"""Format subaru-vehicle.sh JSON stdout for Nextcloud Talk replies."""

from __future__ import annotations

import json
import os
import sys
from typing import Any


def _refresh_max_age_s() -> float:
    try:
        return float(os.environ.get("SUBARU_TALK_REFRESH_MAX_AGE_S", "300"))
    except ValueError:
        return 300.0


def _age_label(stale_s: Any) -> str | None:
    """Human 'Updated Xm/Xh ago' from staleness seconds; minutes under 2h."""
    try:
        secs = float(stale_s)
    except (TypeError, ValueError):
        return None
    if secs < 0:
        return None
    mins = int(secs // 60)
    if mins < 120:
        return f"Updated {mins}m ago"
    return f"Updated {int(secs // 3600)}h ago"


def _maps_url(lat: Any, lon: Any) -> str:
    return f"https://www.google.com/maps?q={lat},{lon}"


def _place_label(lat: Any, lon: Any) -> str | None:
    """Best-effort reverse-geocoded place name. None unless SUBARU_GEOCODE=1 or cached."""
    try:
        from subaru_geocode import reverse_geocode
    except ImportError:
        return None
    openclaw_dir = os.environ.get("OPENCLAW_DIR") or os.path.expanduser("~/.openclaw")
    cache_path = os.path.join(openclaw_dir, "state", "subaru-geocode-cache.json")
    return reverse_geocode(lat, lon, cache_path=cache_path)


def _format_status(payload: dict[str, Any]) -> str:
    nick = payload.get("nickname") or "Subaru"
    data = payload.get("data") or {}
    vs = data.get("vehicle_status") or {}
    health = data.get("vehicle_health") or {}
    meta = data.get("meta") or {}
    stale = meta.get("staleness_seconds")
    if stale is None:
        stale = vs.get("staleness_seconds")

    max_age = _refresh_max_age_s()
    is_stale = isinstance(stale, (int, float)) and stale > max_age

    lines = [nick]
    if is_stale:
        mins = int(stale // 60)
        age = f"{mins}m" if mins < 120 else f"{int(stale // 3600)}h"
        lines.append(f"(cached ~{age} old - could not refresh)")

    odo = vs.get("ODOMETER")
    if odo is not None:
        lines.append(f"Odometer: {odo} mi")
    dist = vs.get("DISTANCE_TO_EMPTY_FUEL")
    if dist is not None:
        lines.append(f"Range: {dist} mi")
    fuel = vs.get("REMAINING_FUEL_PERCENT")
    if fuel is not None:
        lines.append(f"Fuel: {fuel}%")
    state = vs.get("VEHICLE_STATE_TYPE")
    if state:
        lines.append(f"Ignition: {state}")

    door_bits = []
    for key, label in (
        ("DOOR_BOOT_POSITION", "boot"),
        ("DOOR_FRONT_LEFT_POSITION", "FL"),
        ("DOOR_FRONT_RIGHT_POSITION", "FR"),
        ("DOOR_REAR_LEFT_POSITION", "RL"),
        ("DOOR_REAR_RIGHT_POSITION", "RR"),
    ):
        val = vs.get(key)
        if val and str(val).upper() != "CLOSED":
            door_bits.append(f"{label} {str(val).lower()}")
    if door_bits:
        lines.append("Doors: " + ", ".join(door_bits))
    elif vs.get("DOOR_BOOT_POSITION"):
        lines.append("Doors: all closed")

    lock = vs.get("VEHICLE_LOCK_STATUS") or vs.get("DOOR_LOCK_STATUS")
    if lock:
        lines.append(f"Locks: {str(lock).lower()}")

    if (
        vs.get("LOCATION_VALID")
        and vs.get("LATITUDE") is not None
        and vs.get("LONGITUDE") is not None
    ):
        place = _place_label(vs.get("LATITUDE"), vs.get("LONGITUDE"))
        loc_line = f"Location: {_maps_url(vs.get('LATITUDE'), vs.get('LONGITUDE'))}"
        if place:
            loc_line = f"Location: {place} — {_maps_url(vs.get('LATITUDE'), vs.get('LONGITUDE'))}"
        lines.append(loc_line)

    if health.get("ISTROUBLE"):
        lines.append("Warning: MIL/trouble active")

    if not is_stale:
        age = _age_label(stale)
        if age:
            lines.append(age)

    if len(lines) == 1:
        text = data.get("summary_text")
        if text:
            return text if str(text).startswith(nick) else f"{nick}\n{text}"
        return f"{nick}: status ok (no cached telemetry - try fetch)"
    return "\n".join(lines)


def format_talk_reply(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        code = payload.get("error_code") or "subaru_api"
        errs = payload.get("errors") or []
        detail = errs[0] if errs and str(errs[0]) else code
        hints = {
            "auth_invalid": "Check ~/.openclaw/.env.d/subaru-password after a MySubaru password change.",
            "account_locked": "MySubaru account locked — wait 30–60 min before retrying 2FA.",
            "device_not_authenticated": "Run: bash ~/.openclaw/scripts/subaru-device-register.sh --request",
            "pin_missing": "Add your 4-digit PIN to ~/.openclaw/.env.d/subaru-pin",
            "actuation_disabled": "Actuation is off (read-only commands still work).",
        }
        hint = hints.get(code, "")
        lines = [f"Subaru ({payload.get('nickname') or 'vehicle'}): {code}"]
        if detail and detail != code:
            lines.append(str(detail)[:200])
        if hint:
            lines.append(hint)
        return "\n".join(lines)

    cmd = payload.get("command") or "status"
    nick = payload.get("nickname") or "Subaru"
    data = payload.get("data") or {}

    if cmd in ("summary", "status", "show", "fetch", "update", "condition"):
        return _format_status(payload)

    if cmd == "health-report":
        score = data.get("score")
        verdict = data.get("verdict")
        return f"{nick} health: score {score}/100 ({verdict})"

    if cmd == "locate":
        lat, lon = data.get("lat"), data.get("lon")
        url = data.get("maps_url")
        if lat is not None and lon is not None:
            place = _place_label(lat, lon)
            line = f"{nick} at {place}" if place else f"{nick} at {lat}, {lon}"
            if url:
                line += f"\n{url}"
            return line
        return f"{nick}: locate returned no GPS fix"

    if cmd == "capabilities":
        remote = data.get("remote_status")
        res = data.get("res_status")
        return f"{nick} remote={remote} RES={res}"

    return f"{nick}: {cmd} ok"


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        print("Subaru: empty response", file=sys.stderr)
        return 1
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print(raw.strip()[:500])
        return 0
    print(format_talk_reply(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
