#!/usr/bin/env python3
"""Format subaru-vehicle.sh JSON stdout for Nextcloud Talk replies."""

from __future__ import annotations

import json
import sys
from typing import Any


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

    if cmd in ("summary", "status", "show", "fetch", "update"):
        text = data.get("summary_text")
        if not text:
            vs = data.get("vehicle_status") or {}
            if isinstance(data.get("vehicle_status"), dict) and "vehicle_status" in data:
                vs = data["vehicle_status"]
            parts = [nick]
            odo = vs.get("ODOMETER")
            if odo is not None:
                parts.append(f"Odometer: {odo} mi")
            fuel = vs.get("REMAINING_FUEL_PERCENT")
            if fuel is not None:
                parts.append(f"Fuel: {fuel}%")
            dist = vs.get("DISTANCE_TO_EMPTY_FUEL")
            if dist is not None:
                parts.append(f"Range: {dist} mi")
            state = vs.get("VEHICLE_STATE_TYPE")
            if state:
                parts.append(f"State: {state}")
            text = "\n".join(parts) if len(parts) > 1 else None
        return text or f"{nick}: status ok (no cached telemetry — try fetch)"

    if cmd == "health-report":
        score = data.get("score")
        verdict = data.get("verdict")
        return f"{nick} health: score {score}/100 ({verdict})"

    if cmd == "locate":
        lat, lon = data.get("lat"), data.get("lon")
        url = data.get("maps_url")
        if lat is not None and lon is not None:
            line = f"{nick} at {lat}, {lon}"
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
