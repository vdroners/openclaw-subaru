"""Health scorecard for MySubaru telemetry (no network)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class HealthCheck:
    check_id: str
    status: str  # pass | warn | fail
    message: str


def _psi_low(actual: float, recommended: float, warn_pct: float, fail_pct: float) -> str | None:
    if recommended <= 0 or actual <= 0:
        return "fail" if actual <= 0 else None
    ratio = actual / recommended
    if ratio < (1.0 - fail_pct):
        return "fail"
    if ratio < (1.0 - warn_pct):
        return "warn"
    return None


def _psi_high(actual: float, recommended: float, warn_pct: float, fail_pct: float) -> str | None:
    if recommended <= 0 or actual <= 0:
        return None
    ratio = actual / recommended
    if ratio > (1.0 + fail_pct):
        return "fail"
    if ratio > (1.0 + warn_pct):
        return "warn"
    return None


def evaluate_health(
    status: dict[str, Any],
    health: dict[str, Any],
    capabilities: dict[str, Any],
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return scorecard dict with checks[], score, verdict."""
    thresholds = thresholds or {}
    fuel_warn = float(thresholds.get("fuel_percent_warn", 15))
    fuel_fail = float(thresholds.get("fuel_percent_fail", 5))
    range_warn = float(thresholds.get("fuel_range_miles_warn", 30))
    range_fail = float(thresholds.get("fuel_range_miles_fail", 10))
    stale_warn_h = float(thresholds.get("staleness_hours_warn", 24))
    stale_fail_h = float(thresholds.get("staleness_hours_fail", 72))

    checks: list[HealthCheck] = []
    worst = 0

    def add(check_id: str, status_level: str, message: str) -> None:
        nonlocal worst
        checks.append(HealthCheck(check_id, status_level, message))
        if status_level == "fail":
            worst = max(worst, 2)
        elif status_level == "warn":
            worst = max(worst, 1)

    if health.get("ISTROUBLE") or health.get("HEALTH_TROUBLE"):
        add("H-MIL", "fail", "Vehicle health reports MIL/trouble active")

    rec = health.get("RECOMMENDED_TIRE_PRESSURE") or {}
    front_rec = float(rec.get("FRONT_TIRES") or 0)
    rear_rec = float(rec.get("REAR_TIRES") or 0)
    tpms_map = [
        ("FL", status.get("TYRE_PRESSURE_FRONT_LEFT"), front_rec),
        ("FR", status.get("TYRE_PRESSURE_FRONT_RIGHT"), front_rec),
        ("RL", status.get("TYRE_PRESSURE_REAR_LEFT"), rear_rec),
        ("RR", status.get("TYRE_PRESSURE_REAR_RIGHT"), rear_rec),
    ]
    if capabilities.get("has_tpms"):
        for label, psi, rec_psi in tpms_map:
            try:
                val = float(psi or 0)
            except (TypeError, ValueError):
                val = 0.0
            low = _psi_low(val, rec_psi, 0.15, 0.25)
            high = _psi_high(val, rec_psi, 0.20, 0.30)
            if low == "fail":
                add("H-TPMS-LOW", "fail", f"Tire {label} critically low ({val} psi)")
            elif low == "warn":
                add("H-TPMS-LOW", "warn", f"Tire {label} low ({val} psi)")
            if high == "fail":
                add("H-TPMS-HIGH", "fail", f"Tire {label} critically high ({val} psi)")
            elif high == "warn":
                add("H-TPMS-HIGH", "warn", f"Tire {label} high ({val} psi)")

    fuel_pct = status.get("REMAINING_FUEL_PERCENT")
    if fuel_pct is not None:
        try:
            fp = float(fuel_pct)
            if fp < fuel_fail:
                add("H-FUEL-PCT", "fail", f"Fuel {fp:.0f}%")
            elif fp < fuel_warn:
                add("H-FUEL-PCT", "warn", f"Fuel {fp:.0f}%")
        except (TypeError, ValueError):
            pass

    dist_empty = status.get("DISTANCE_TO_EMPTY_FUEL")
    if dist_empty is not None:
        try:
            de = float(dist_empty)
            if de < range_fail:
                add("H-FUEL-RNG", "fail", f"Range {de:.0f} mi")
            elif de < range_warn:
                add("H-FUEL-RNG", "warn", f"Range {de:.0f} mi")
        except (TypeError, ValueError):
            pass

    door_keys = [
        "DOOR_FRONT_LEFT_POSITION",
        "DOOR_FRONT_RIGHT_POSITION",
        "DOOR_REAR_LEFT_POSITION",
        "DOOR_REAR_RIGHT_POSITION",
        "DOOR_BOOT_POSITION",
        "DOOR_ENGINE_HOOD_POSITION",
    ]
    for key in door_keys:
        if str(status.get(key, "")).upper() == "OPEN":
            add("H-DOOR", "warn", f"{key} is OPEN")

    for key in status:
        if key.startswith("LOCK_") and key.endswith("_STATUS"):
            if str(status.get(key, "")).upper() == "UNLOCKED":
                add("H-LOCK", "warn", f"{key} is UNLOCKED")

    for key in status:
        if key.startswith("WINDOW_") and key.endswith("_STATUS"):
            val = str(status.get(key, "")).upper()
            if val in ("OPEN", "VENTED"):
                add("H-WINDOW", "warn", f"{key} is {val}")

    sunroof = status.get("WINDOW_SUNROOF_STATUS")
    if sunroof and str(sunroof).upper() not in ("CLOSE", "CLOSED", "UNKNOWN", ""):
        add("H-SUNROOF", "warn", f"Sunroof status {sunroof}")

    stale_s = status.get("staleness_seconds")
    if stale_s is None and status.get("TIMESTAMP"):
        ts = status["TIMESTAMP"]
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                stale_s = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()
            except ValueError:
                stale_s = None
        elif isinstance(ts, datetime):
            stale_s = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
    if stale_s is not None:
        hours = float(stale_s) / 3600.0
        if hours > stale_fail_h:
            add("H-STALE", "fail", f"Data stale {hours:.0f}h")
        elif hours > stale_warn_h:
            add("H-STALE", "warn", f"Data stale {hours:.0f}h")

    if capabilities.get("subscription_status") is False:
        add("H-SUB", "fail", "MySubaru subscription inactive")
    if capabilities.get("res_status") is False:
        add("H-RES", "warn", "Remote engine start not available")

    if str(status.get("VEHICLE_STATE_TYPE", "")).upper() == "IGNITION_ON":
        add("H-IGNITION", "warn", "Vehicle reports ignition ON")

    if capabilities.get("ev"):
        soc = status.get("EV_STATE_OF_CHARGE_PERCENT")
        if soc is not None:
            try:
                s = float(soc)
                if s < 10:
                    add("H-EV-SOC", "fail", f"EV SOC {s:.0f}%")
                elif s < 20:
                    add("H-EV-SOC", "warn", f"EV SOC {s:.0f}%")
            except (TypeError, ValueError):
                pass

    if not checks:
        checks.append(HealthCheck("H-OK", "pass", "No issues detected"))

    score = 100
    for c in checks:
        if c.status == "fail":
            score -= 25
        elif c.status == "warn":
            score -= 10
    score = max(0, min(100, score))

    verdict = "pass"
    if worst >= 2:
        verdict = "fail"
    elif worst == 1:
        verdict = "warn"

    return {
        "score": score,
        "verdict": verdict,
        "checks": [{"id": c.check_id, "status": c.status, "message": c.message} for c in checks],
    }


def exception_to_error_code(exc: BaseException) -> str:
    name = type(exc).__name__
    mapping = {
        "InvalidCredentials": "auth_invalid",
        "IncompleteCredentials": "auth_incomplete",
        "InvalidPIN": "pin_invalid",
        "PINLockoutProtect": "pin_lockout",
        "VehicleNotSupported": "unsupported",
        "RemoteServiceFailure": "remote_failed",
        "SubaruException": "subaru_api",
    }
    return mapping.get(name, "subaru_api")
