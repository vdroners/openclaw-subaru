"""Mocked _run_live tests for status/update/throttle/charge error mapping.

Uses a fake subarulink Controller so the live code path is exercised without any
network or credentials.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "lib"))

from subaru_core import Settings, SubaruRunner  # noqa: E402


class FakeController:
    def __init__(self, ev=False):
        self.device_registered = True
        self._ev = ev
        self.update_calls = 0
        self.fetch_calls = 0

    async def get_data(self, vin):
        return {
            "vehicle_status": {
                "ODOMETER": 42000,
                "REMAINING_FUEL_PERCENT": 55,
                "TIMESTAMP": datetime.now(timezone.utc).isoformat(),
            },
            "vehicle_health": {"ISTROUBLE": False},
        }

    async def fetch(self, vin):
        self.fetch_calls += 1
        return True

    async def update(self, vin, force=False):
        self.update_calls += 1
        return True

    # Sync capability getters
    def get_remote_status(self, vin):
        return True

    def get_res_status(self, vin):
        return True

    def get_safety_status(self, vin):
        return True

    def get_subscription_status(self, vin):
        return True

    def has_tpms(self, vin):
        return True

    async def has_lock_status(self, vin):
        return True

    async def has_power_windows(self, vin):
        return True

    def has_sunroof(self, vin):
        return False

    def get_ev_status(self, vin):
        return self._ev

    def get_api_gen(self, vin):
        return "g2"

    def get_model_year(self, vin):
        return "2022"

    def get_model_name(self, vin):
        return "Outback"

    def vin_to_name(self, vin):
        return "Outback"

    def is_pin_required(self):
        return True

    def get_last_fetch_time(self, vin):
        return None

    def get_last_update_time(self, vin):
        return None

    def get_vehicles(self):
        return ["VIN123"]


def _runner(tmp_path, *, ev=False, interval=0):
    os.environ["OPENCLAW_DIR"] = str(tmp_path)
    os.environ["SUBARU_UPDATE_MIN_INTERVAL_S"] = str(interval)
    try:
        settings = Settings(dry_run=False)
    finally:
        os.environ.pop("OPENCLAW_DIR", None)
        os.environ.pop("SUBARU_UPDATE_MIN_INTERVAL_S", None)
    settings.enabled = True
    settings.actuation_enabled = True
    settings.pin = "1234"
    settings.vin = "VIN123"
    settings.audit_log = tmp_path / "audit.jsonl"
    settings.openclaw_dir = tmp_path
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "subaru-gates-live-pass.json").write_text(
        json.dumps(
            {
                "passed_at": "2026-01-01T00:00:00Z",
                "gates": {
                    "SUB-LIVE-LOCK": True,
                    "SUB-LIVE-UNLOCK": True,
                    "SUB-LIVE-START": True,
                    "SUB-LIVE-STOP": True,
                },
            }
        ),
        encoding="utf-8",
    )
    runner = SubaruRunner(settings)
    runner._ctrl = FakeController(ev=ev)
    return runner


def test_live_status_bundle(tmp_path):
    runner = _runner(tmp_path)
    resp = asyncio.run(runner._run_live("status", {}))
    assert resp["ok"] is True
    assert resp["data"]["vehicle_status"]["ODOMETER"] == 42000
    assert "staleness_seconds" in resp["data"]["meta"]


def test_live_update_calls_controller(tmp_path):
    runner = _runner(tmp_path, interval=0)
    resp = asyncio.run(runner._run_live("update", {}))
    assert resp["ok"] is True
    assert resp["data"]["updated"] is True
    assert runner._ctrl.update_calls == 1


def test_live_update_throttled_serves_cache(tmp_path):
    runner = _runner(tmp_path, interval=600)
    runner.settings.update_state.parent.mkdir(parents=True, exist_ok=True)
    runner.settings.update_state.write_text(
        json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()}), encoding="utf-8"
    )
    resp = asyncio.run(runner._run_live("update", {}))
    assert resp["ok"] is True
    assert resp["data"]["updated"] is False
    assert resp["data"]["throttled"] is True
    assert runner._ctrl.update_calls == 0  # coalesced


def test_charge_unsupported_maps_error_code(tmp_path):
    # The charge handler raises RuntimeError("unsupported") on a non-EV; run()
    # must surface that as error_code "unsupported" (not the generic subaru_api).
    runner = _runner(tmp_path, ev=False)

    async def boom(command, args):
        raise RuntimeError("unsupported")

    runner._run_live = boom  # type: ignore[assignment]
    resp = asyncio.run(runner.run("charge", {}))
    assert resp["ok"] is False
    assert resp["error_code"] == "unsupported"
