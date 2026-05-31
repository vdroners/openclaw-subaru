#!/usr/bin/env python3
"""MySubaru / subarulink integration core for OpenClaw Subaru."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from subaru_health import evaluate_health, exception_to_error_code  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_STATUS = ROOT / "tests" / "subaru" / "fixtures" / "status_ok.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_secret(path: str | None) -> str:
    if not path:
        return ""
    p = Path(os.path.expanduser(path))
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8").strip()


def _load_vehicle_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(os.path.expanduser(path))
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _save_vehicle_json(path: str | None, data: dict[str, Any]) -> None:
    if not path:
        raise ValueError("SUBARU_VEHICLE_JSON not configured")
    p = Path(os.path.expanduser(path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _maps_url(lat: float | None, lon: float | None) -> str | None:
    if lat is None or lon is None:
        return None
    return f"https://www.google.com/maps?q={lat},{lon}"


def _redact_raw(raw: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(_json_safe(raw))
    for key in ("password", "pin", "token", "session"):
        if key in text.lower():
            pass
    return _json_safe(raw)


class Settings:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run or os.environ.get("SUBARU_DRY_RUN", "") == "1"
        self.enabled = os.environ.get("SUBARU_ENABLED", "0") == "1"
        self.username = os.environ.get("SUBARU_USERNAME", "").strip()
        self.password = _read_secret(os.environ.get("SUBARU_PASSWORD_FILE"))
        self.pin = _read_secret(os.environ.get("SUBARU_PIN_FILE"))
        self.vin = os.environ.get("SUBARU_VIN", "").strip()
        self.country = os.environ.get("SUBARU_COUNTRY", "USA").strip() or "USA"
        self.actuation_enabled = os.environ.get("SUBARU_ACTUATION_ENABLED", "0") == "1"
        self.openclaw_dir = Path(os.environ.get("OPENCLAW_DIR", Path.home() / ".openclaw"))
        self.vehicle_json_path = os.environ.get(
            "SUBARU_VEHICLE_JSON",
            str(self.openclaw_dir / "config" / "subaru-vehicle.json"),
        )
        self.vehicle_cfg = _load_vehicle_json(self.vehicle_json_path)
        if not self.vin:
            self.vin = str(self.vehicle_cfg.get("vin") or "").strip()
        self.nickname = str(self.vehicle_cfg.get("nickname") or "Subaru").strip()
        self.default_preset = str(self.vehicle_cfg.get("remote_start_preset") or "").strip()
        self.device_id = int(
            self.vehicle_cfg.get("device_id")
            or os.environ.get("SUBARU_DEVICE_ID")
            or 1234567890
        )
        self.device_name = str(
            self.vehicle_cfg.get("device_name")
            or os.environ.get("SUBARU_DEVICE_NAME")
            or "openclaw-homelab"
        )
        self.locate_min_hours = float(os.environ.get("SUBARU_LOCATE_MIN_INTERVAL_H", "2"))
        self.locate_state = self.openclaw_dir / "state" / "subaru-locate-last.json"
        self.maps_state = self.openclaw_dir / "state" / "subaru-last-location.json"
        self.audit_log = self.openclaw_dir / "state" / "subaru-command-log.jsonl"
        self.thresholds = self.vehicle_cfg.get("alert_thresholds") or {}


def load_dry_fixture() -> dict[str, Any]:
    if FIXTURE_STATUS.is_file():
        return json.loads(FIXTURE_STATUS.read_text(encoding="utf-8"))
    return {
        "ok": True,
        "command": "status",
        "vin": self.settings.vin or "4S4BRCKC8N3400001",
        "nickname": "Outback",
        "timestamp": utc_now_iso(),
        "capabilities": {"remote_status": True, "res_status": True},
        "data": {},
        "warnings": [],
        "errors": [],
        "error_code": None,
    }


def make_response(
    *,
    ok: bool,
    command: str,
    settings: Settings,
    data: dict[str, Any] | None = None,
    capabilities: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "command": command,
        "vin": settings.vin or None,
        "nickname": settings.nickname,
        "timestamp": utc_now_iso(),
        "capabilities": capabilities,
        "data": data or {},
        "warnings": warnings or [],
        "errors": errors or [],
        "error_code": error_code,
    }


def validate_response_envelope(payload: dict[str, Any]) -> list[str]:
    required = ("ok", "command", "timestamp", "data", "warnings", "errors")
    missing = [k for k in required if k not in payload]
    return [f"missing key {k}" for k in missing]


class SubaruRunner:
    ACTUATION_COMMANDS = frozenset(
        {
            "lock",
            "unlock",
            "start",
            "remote_start",
            "stop",
            "remote_stop",
            "horn",
            "lights",
            "charge",
            "presets-add",
            "presets-delete",
            "presets-default",
        }
    )
    TIER3 = frozenset({"unlock", "start", "remote_start"})

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._ctrl = None
        self._session = None

    def _ensure_enabled(self) -> None:
        if self.settings.dry_run:
            return
        if not self.settings.enabled:
            raise RuntimeError("SUBARU_ENABLED is not set")

    def _ensure_actuation(self, command: str) -> None:
        if command in ("horn", "lights") and str(os.environ.get("SUBARU_ARGS_STOP", "")) == "1":
            return
        if command not in self.ACTUATION_COMMANDS:
            return
        if self.settings.dry_run:
            return
        if not self.settings.actuation_enabled:
            raise PermissionError("actuation_disabled")
        if not self.settings.pin:
            raise PermissionError("pin_missing")

    def _audit(self, command: str, ok: bool, error_code: str | None, tier: int) -> None:
        if self.settings.dry_run:
            return
        self.settings.audit_log.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": utc_now_iso(),
            "command": command,
            "vin": self.settings.vin,
            "tier": tier,
            "ok": ok,
            "error_code": error_code,
        }
        with self.settings.audit_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    def _check_locate_rate(self, force: bool = False) -> None:
        if self.settings.dry_run or force:
            return
        state_path = self.settings.locate_state
        if not state_path.is_file():
            return
        try:
            last = json.loads(state_path.read_text(encoding="utf-8"))
            ts = datetime.fromisoformat(str(last.get("timestamp")).replace("Z", "+00:00"))
            elapsed_h = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds() / 3600.0
            if elapsed_h < self.settings.locate_min_hours:
                raise RuntimeError("rate_limited")
        except (json.JSONDecodeError, ValueError, TypeError):
            return

    def _record_locate(self, lat: float | None, lon: float | None) -> None:
        payload = {"timestamp": utc_now_iso(), "lat": lat, "lon": lon}
        self.settings.locate_state.parent.mkdir(parents=True, exist_ok=True)
        self.settings.locate_state.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        if lat is not None and lon is not None:
            self.settings.maps_state.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    async def _get_controller(self):
        if self._ctrl is not None:
            return self._ctrl
        import aiohttp
        from subarulink import Controller
        from subarulink import const as sc

        if not self.settings.username or not self.settings.password:
            raise RuntimeError("auth_incomplete")
        country = sc.COUNTRY_CAN if self.settings.country.upper() == "CANADA" else sc.COUNTRY_USA
        self._session = aiohttp.ClientSession()
        self._ctrl = Controller(
            self._session,
            self.settings.username,
            self.settings.password,
            self.settings.device_id,
            self.settings.pin,
            self.settings.device_name,
            country=country,
        )
        if not await self._ctrl.connect():
            raise RuntimeError("auth_invalid")
        return self._ctrl

    async def _close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._ctrl = None

    async def _capabilities_async(self, ctrl, vin: str) -> dict[str, Any]:
        data = await ctrl.get_data(vin)
        return {
            "remote_status": ctrl.get_remote_status(vin),
            "res_status": ctrl.get_res_status(vin),
            "safety_status": ctrl.get_safety_status(vin),
            "subscription_status": ctrl.get_subscription_status(vin),
            "has_tpms": ctrl.has_tpms(vin),
            "has_lock_status": await ctrl.has_lock_status(vin),
            "has_power_windows": await ctrl.has_power_windows(vin),
            "has_sunroof": ctrl.has_sunroof(vin),
            "ev": ctrl.get_ev_status(vin),
            "api_gen": ctrl.get_api_gen(vin),
            "model_year": ctrl.get_model_year(vin),
            "model_name": ctrl.get_model_name(vin),
            "vehicle_name": ctrl.vin_to_name(vin),
            "subscription_features": list(data.get("subscription_features") or []),
            "vehicle_features": list(data.get("vehicle_features") or []),
            "device_registered": ctrl.device_registered(),
            "pin_required": ctrl.is_pin_required(),
        }

    def _status_bundle(self, ctrl, vin: str, data: dict[str, Any]) -> dict[str, Any]:
        status = _json_safe(dict(data.get("vehicle_status") or {}))
        health = _json_safe(dict(data.get("vehicle_health") or {}))
        ts = status.get("TIMESTAMP")
        stale = None
        if ts:
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                stale = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()
            except ValueError:
                stale = None
        status["staleness_seconds"] = stale
        return {
            "vehicle_status": status,
            "vehicle_health": health,
            "meta": {
                "last_fetch": _json_safe(ctrl.get_last_fetch_time(vin)),
                "last_update": _json_safe(ctrl.get_last_update_time(vin)),
                "staleness_seconds": stale,
            },
        }

    def _summary_text(self, status: dict[str, Any], health: dict[str, Any]) -> str:
        lines = []
        odo = status.get("ODOMETER")
        if odo is not None:
            lines.append(f"Odometer: {odo} miles")
        dist = status.get("DISTANCE_TO_EMPTY_FUEL")
        if dist is not None:
            lines.append(f"Distance to empty: {dist} miles")
        fuel = status.get("REMAINING_FUEL_PERCENT")
        if fuel is not None:
            lines.append(f"Fuel: {fuel}%")
        state = status.get("VEHICLE_STATE_TYPE")
        if state:
            lines.append(f"Vehicle state: {state}")
        if status.get("LOCATION_VALID") and status.get("LATITUDE") and status.get("LONGITUDE"):
            lines.append(
                f"Position: {status.get('LATITUDE')}N {float(status.get('LONGITUDE')) * -1}W"
            )
        if health.get("ISTROUBLE"):
            lines.append("MIL/trouble: active")
        stale = status.get("staleness_seconds")
        if stale is not None:
            lines.append(f"Data age: {int(float(stale) // 3600)}h")
        return "\n".join(lines) if lines else "No summary data available"

    async def run(self, command: str, args: dict[str, Any]) -> dict[str, Any]:
        if self.settings.dry_run:
            return self._run_dry(command, args)

        self._ensure_enabled()
        tier = 3 if command in self.TIER3 else (2 if command in self.ACTUATION_COMMANDS else 0)
        try:
            self._ensure_actuation(command)
            result = await self._run_live(command, args)
            self._audit(command, result.get("ok", False), result.get("error_code"), tier)
            return result
        except PermissionError as exc:
            code = str(exc.args[0]) if exc.args else "actuation_disabled"
            resp = make_response(
                ok=False,
                command=command,
                settings=self.settings,
                errors=[code],
                error_code=code,
            )
            self._audit(command, False, code, tier)
            return resp
        except RuntimeError as exc:
            msg = str(exc)
            code = msg if msg in ("rate_limited", "auth_incomplete", "auth_invalid", "preset_missing") else "subaru_api"
            return make_response(ok=False, command=command, settings=self.settings, errors=[msg], error_code=code)
        except Exception as exc:
            code = exception_to_error_code(exc)
            return make_response(
                ok=False,
                command=command,
                settings=self.settings,
                errors=[str(exc)],
                error_code=code,
            )
        finally:
            await self._close()

    def _run_dry(self, command: str, args: dict[str, Any]) -> dict[str, Any]:
        base = load_dry_fixture()
        caps = base.get("capabilities") or {}
        data = dict(base.get("data") or {})
        if command in ("start", "remote_start", "lock", "unlock", "horn", "lights", "charge", "stop", "remote_stop"):
            if not self.settings.actuation_enabled and os.environ.get("SUBARU_DRY_RUN") != "force-actuation":
                return make_response(
                    ok=False,
                    command=command,
                    settings=self.settings,
                    errors=["actuation_disabled"],
                    error_code="actuation_disabled",
                )
        if command == "locate":
            lat = data.get("vehicle_status", {}).get("LATITUDE", 45.5231)
            lon = data.get("vehicle_status", {}).get("LONGITUDE", -122.6765)
            return make_response(
                ok=True,
                command=command,
                settings=self.settings,
                capabilities=caps,
                data={"lat": lat, "lon": lon, "maps_url": _maps_url(lat, lon), "accuracy_note": "dry-run"},
            )
        if command == "health-report":
            bundle = evaluate_health(
                data.get("vehicle_status") or {},
                data.get("vehicle_health") or {},
                caps,
                self.settings.thresholds,
            )
            return make_response(ok=True, command=command, settings=self.settings, capabilities=caps, data=bundle)
        if command == "summary":
            status = data.get("vehicle_status") or {}
            health = data.get("vehicle_health") or {}
            text = self._summary_text(status, health)
            return make_response(
                ok=True,
                command=command,
                settings=self.settings,
                capabilities=caps,
                data={"summary_text": text, **data},
            )
        if command == "maps-link":
            return make_response(
                ok=True,
                command=command,
                settings=self.settings,
                data={"maps_url": "https://www.google.com/maps?q=45.5231,-122.6765"},
            )
        if command == "presets-list":
            return make_response(ok=True, command=command, settings=self.settings, data={"presets": ["Default", "Winter"]})
        if command == "auth-check":
            return make_response(
                ok=True,
                command=command,
                settings=self.settings,
                data={"device_registered": True, "session_configured": True},
            )
        if command == "vehicles-list":
            return make_response(
                ok=True,
                command=command,
                settings=self.settings,
                data={"vehicles": [{"vin": self.settings.vin or base.get("vin"), "name": self.settings.nickname}]},
            )
        return make_response(
            ok=True,
            command=command,
            settings=self.settings,
            capabilities=caps,
            data=data if command in ("status", "show", "condition", "health", "capabilities", "fetch", "update", "raw") else {},
        )

    async def _run_live(self, command: str, args: dict[str, Any]) -> dict[str, Any]:
        ctrl = await self._get_controller()
        vin = str(args.get("vin") or self.settings.vin)
        if not vin:
            vins = ctrl.get_vehicles()
            if not vins:
                raise RuntimeError("auth_invalid")
            vin = vins[0]
        caps = await self._capabilities_async(ctrl, vin)

        if command in ("status", "show", "summary", "health", "condition", "capabilities"):
            data = await ctrl.get_data(vin)
            bundle = self._status_bundle(ctrl, vin, data)
            if command == "capabilities":
                return make_response(ok=True, command=command, settings=self.settings, capabilities=caps, data=caps)
            if command == "health":
                return make_response(
                    ok=True,
                    command=command,
                    settings=self.settings,
                    capabilities=caps,
                    data={"vehicle_health": bundle["vehicle_health"]},
                )
            if command == "condition":
                return make_response(
                    ok=True,
                    command=command,
                    settings=self.settings,
                    capabilities=caps,
                    data={"vehicle_status": bundle["vehicle_status"]},
                )
            if command == "summary":
                text = self._summary_text(bundle["vehicle_status"], bundle["vehicle_health"])
                return make_response(
                    ok=True,
                    command=command,
                    settings=self.settings,
                    capabilities=caps,
                    data={"summary_text": text, **bundle},
                )
            if command == "show":
                return make_response(
                    ok=True,
                    command=command,
                    settings=self.settings,
                    capabilities=caps,
                    data=_json_safe(data),
                )
            return make_response(ok=True, command=command, settings=self.settings, capabilities=caps, data=bundle)

        if command == "raw":
            raw = ctrl.get_raw_data(vin)
            return make_response(
                ok=True,
                command=command,
                settings=self.settings,
                capabilities=caps,
                data={"raw_redacted": _redact_raw(raw)},
            )

        if command == "fetch":
            ok = await ctrl.fetch(vin)
            data = await ctrl.get_data(vin)
            bundle = self._status_bundle(ctrl, vin, data)
            return make_response(
                ok=bool(ok),
                command=command,
                settings=self.settings,
                capabilities=caps,
                data={"refreshed": bool(ok), **bundle},
            )

        if command == "update":
            ok = await ctrl.update(vin)
            data = await ctrl.get_data(vin)
            bundle = self._status_bundle(ctrl, vin, data)
            return make_response(
                ok=bool(ok),
                command=command,
                settings=self.settings,
                capabilities=caps,
                data={"updated": bool(ok), **bundle},
            )

        if command == "locate":
            self._check_locate_rate(force=bool(args.get("force")))
            ok = await ctrl.update(vin, force=True)
            data = await ctrl.get_data(vin)
            status = _json_safe(dict(data.get("vehicle_status") or {}))
            lat = status.get("LATITUDE")
            lon = status.get("LONGITUDE")
            if lat is not None and lon is not None:
                self._record_locate(float(lat), float(lon))
            return make_response(
                ok=bool(ok),
                command=command,
                settings=self.settings,
                capabilities=caps,
                data={
                    "lat": lat,
                    "lon": lon,
                    "maps_url": _maps_url(float(lat) if lat is not None else None, float(lon) if lon is not None else None),
                    "accuracy_note": "Locate wakes vehicle; do not poll more often than SUBARU_LOCATE_MIN_INTERVAL_H",
                    "vehicle_status": status,
                },
            )

        if command == "maps-link":
            if self.settings.maps_state.is_file():
                loc = json.loads(self.settings.maps_state.read_text(encoding="utf-8"))
                lat, lon = loc.get("lat"), loc.get("lon")
            else:
                data = await ctrl.get_data(vin)
                status = data.get("vehicle_status") or {}
                lat, lon = status.get("LATITUDE"), status.get("LONGITUDE")
            return make_response(
                ok=True,
                command=command,
                settings=self.settings,
                capabilities=caps,
                data={"maps_url": _maps_url(float(lat) if lat else None, float(lon) if lon else None)},
            )

        if command == "health-report":
            if args.get("prefetch"):
                await ctrl.fetch(vin)
            data = await ctrl.get_data(vin)
            bundle = self._status_bundle(ctrl, vin, data)
            report = evaluate_health(
                bundle["vehicle_status"],
                bundle["vehicle_health"],
                caps,
                self.settings.thresholds,
            )
            return make_response(ok=True, command=command, settings=self.settings, capabilities=caps, data=report)

        if command == "presets-list":
            presets = await ctrl.list_climate_preset_names(vin)
            return make_response(ok=True, command=command, settings=self.settings, capabilities=caps, data={"presets": presets})

        if command == "presets-show":
            presets = await ctrl.get_user_climate_preset_data(vin)
            return make_response(
                ok=True,
                command=command,
                settings=self.settings,
                capabilities=caps,
                data={"presets_detail": _json_safe(presets)},
            )

        if command == "presets-get":
            name = str(args.get("name") or "")
            preset = await ctrl.get_climate_preset_by_name(vin, name)
            return make_response(
                ok=preset is not None,
                command=command,
                settings=self.settings,
                capabilities=caps,
                data={"preset": _json_safe(preset)},
                error_code=None if preset else "preset_missing",
            )

        if command == "presets-default":
            name = str(args.get("name") or "")
            cfg = dict(self.settings.vehicle_cfg)
            cfg["remote_start_preset"] = name
            _save_vehicle_json(self.settings.vehicle_json_path, cfg)
            self.settings.default_preset = name
            return make_response(ok=True, command=command, settings=self.settings, data={"remote_start_preset": name})

        if command == "presets-delete":
            from subarulink.exceptions import SubaruException

            name = str(args.get("name") or "")
            ok = await ctrl.delete_climate_preset_by_name(vin, name)
            if not ok:
                raise SubaruException(f"Failed to delete preset {name}")
            return make_response(ok=True, command=command, settings=self.settings, data={"deleted": name})

        if command == "presets-add":
            preset_file = args.get("preset_file")
            if not preset_file:
                raise RuntimeError("preset_file required")
            new_preset = json.loads(Path(preset_file).read_text(encoding="utf-8"))
            presets = await ctrl.get_user_climate_preset_data(vin)
            presets = list(presets) + [new_preset]
            ok = await ctrl.update_user_climate_presets(vin, presets)
            return make_response(ok=bool(ok), command=command, settings=self.settings, data={"added": new_preset.get("name")})

        if command == "vehicles-list":
            vehicles = [
                {"vin": v, "name": ctrl.vin_to_name(v)} for v in ctrl.get_vehicles()
            ]
            return make_response(ok=True, command=command, settings=self.settings, data={"vehicles": vehicles})

        if command == "vehicles-select":
            new_vin = str(args.get("vin") or "")
            cfg = dict(self.settings.vehicle_cfg)
            cfg["vin"] = new_vin
            _save_vehicle_json(self.settings.vehicle_json_path, cfg)
            self.settings.vin = new_vin
            return make_response(ok=True, command=command, settings=self.settings, data={"vin": new_vin})

        if command == "auth-check":
            return make_response(
                ok=True,
                command=command,
                settings=self.settings,
                data={
                    "device_registered": ctrl.device_registered(),
                    "session_configured": bool(self.settings.username and self.settings.password),
                    "vehicles": ctrl.get_vehicles(),
                },
            )

        if command == "auth-connect":
            ok = await ctrl.connect()
            return make_response(ok=bool(ok), command=command, settings=self.settings, data={"connected": bool(ok)})

        if command == "pin-test":
            ok = await ctrl.test_pin()
            return make_response(ok=bool(ok), command=command, settings=self.settings, data={"pin_valid": bool(ok)})

        if command == "config-set":
            key = str(args.get("key") or "")
            value = int(args.get("value") or 0)
            if key == "fetch-interval":
                ok = ctrl.set_fetch_interval(value)
            elif key == "update-interval":
                ok = ctrl.set_update_interval(value)
            else:
                raise RuntimeError(f"unknown config key {key}")
            return make_response(ok=bool(ok), command=command, settings=self.settings, data={key: value})

        import subarulink.const as sc

        if command == "lock":
            ok = await ctrl.lock(vin)
            return make_response(ok=bool(ok), command=command, settings=self.settings, capabilities=caps, data={"locked": bool(ok)})

        if command == "unlock":
            door = str(args.get("door") or "all").lower()
            if door in ("driver", "drivers"):
                ok = await ctrl.unlock(vin, sc.DRIVERS_DOOR)
            elif door == "tailgate":
                ok = await ctrl.unlock(vin, sc.TAILGATE_DOOR)
            else:
                ok = await ctrl.unlock(vin)
            return make_response(ok=bool(ok), command=command, settings=self.settings, capabilities=caps, data={"unlocked": bool(ok), "door": door})

        if command in ("start", "remote_start"):
            preset = str(args.get("preset") or self.settings.default_preset)
            if not preset:
                raise RuntimeError("preset_missing")
            ok = await ctrl.remote_start(vin, preset)
            return make_response(
                ok=bool(ok),
                command=command,
                settings=self.settings,
                capabilities=caps,
                data={"started": bool(ok), "preset": preset},
            )

        if command in ("stop", "remote_stop"):
            ok = await ctrl.remote_stop(vin)
            return make_response(ok=bool(ok), command=command, settings=self.settings, capabilities=caps, data={"stopped": bool(ok)})

        if command == "horn":
            if args.get("stop"):
                ok = await ctrl.horn_stop(vin)
                return make_response(ok=bool(ok), command=command, settings=self.settings, data={"horn_stopped": bool(ok)})
            ok = await ctrl.horn(vin)
            return make_response(ok=bool(ok), command=command, settings=self.settings, data={"horn": bool(ok)})

        if command == "lights":
            if args.get("stop"):
                ok = await ctrl.lights_stop(vin)
                return make_response(ok=bool(ok), command=command, settings=self.settings, data={"lights_stopped": bool(ok)})
            ok = await ctrl.lights(vin)
            return make_response(ok=bool(ok), command=command, settings=self.settings, data={"lights": bool(ok)})

        if command == "charge":
            if not caps.get("ev"):
                raise RuntimeError("unsupported")
            ok = await ctrl.charge_start(vin)
            return make_response(ok=bool(ok), command=command, settings=self.settings, data={"charging": bool(ok)})

        raise RuntimeError(f"unknown command {command}")


def run_command(command: str, args: dict[str, Any] | None = None, *, dry_run: bool = False) -> dict[str, Any]:
    settings = Settings(dry_run=dry_run)
    runner = SubaruRunner(settings)
    return asyncio.run(runner.run(command, args or {}))


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=False))


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: subaru_core.py <command> [--dry-run] [options]", file=sys.stderr)
        return 2
    dry = "--dry-run" in argv
    if dry:
        argv = [a for a in argv if a != "--dry-run"]
        os.environ["SUBARU_DRY_RUN"] = "1"
    command = argv[0]
    args: dict[str, Any] = {}
    i = 1
    while i < len(argv):
        tok = argv[i]
        if tok == "--preset" and i + 1 < len(argv):
            args["preset"] = argv[i + 1]
            i += 2
            continue
        if tok == "--door" and i + 1 < len(argv):
            args["door"] = argv[i + 1]
            i += 2
            continue
        if tok == "--name" and i + 1 < len(argv):
            args["name"] = argv[i + 1]
            i += 2
            continue
        if tok == "--vin" and i + 1 < len(argv):
            args["vin"] = argv[i + 1]
            i += 2
            continue
        if tok == "--file" and i + 1 < len(argv):
            args["preset_file"] = argv[i + 1]
            i += 2
            continue
        if tok == "--stop":
            args["stop"] = True
            i += 1
            continue
        if tok == "--force":
            args["force"] = True
            i += 1
            continue
        if tok == "--prefetch":
            args["prefetch"] = True
            i += 1
            continue
        if tok.startswith("--") and i + 1 < len(argv):
            args[tok[2:].replace("-", "_")] = argv[i + 1]
            i += 2
            continue
        i += 1
    payload = run_command(command, args, dry_run=dry)
    print_json(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
