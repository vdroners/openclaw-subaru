"""Integration tests: shim HTTP routing, status-alert shell, dispatch-exec refresh."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
LIB = SCRIPTS / "lib"


def _load_shim():
    spec = importlib.util.spec_from_file_location(
        "talk_webhook_shim", SCRIPTS / "talk-webhook-shim.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _talk_create_payload(room: str, text: str, actor_id: str = "users/dad") -> bytes:
    return json.dumps(
        {
            "type": "Create",
            "actor": {"id": actor_id, "name": "Dad"},
            "object": {"content": text},
            "target": {"id": f"https://cloud.example.com/ocs/v2.php/apps/spreed/api/v3/signaling/token/{room}"},
        }
    ).encode()


def test_shim_routes_subaru_command_without_upstream(monkeypatch, tmp_path):
    shim = _load_shim()
    fast_path = tmp_path / "subaru-talk-fast-path.sh"
    fast_path.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    fast_path.chmod(0o755)

    calls: list[str] = []
    real_expanduser = os.path.expanduser

    def fake_expanduser(p):
        if "subaru-talk-fast-path" in p:
            return str(fast_path)
        return real_expanduser(p)

    def fake_run(cmd, **kwargs):
        calls.append(" ".join(cmd))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(shim.subprocess, "run", fake_run)
    monkeypatch.setattr(shim.os.path, "expanduser", fake_expanduser)
    monkeypatch.setattr(shim.os.path, "isfile", lambda p: True if "subaru-talk-fast-path" in p else os.path.isfile(p))
    monkeypatch.setattr(shim, "is_subaru_command", lambda text, name: "subaru status" in text.lower())

    server = HTTPServer(("127.0.0.1", 0), shim.ShimHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/nextcloud-talk-webhook",
            data=_talk_create_payload("room1", "@openclaw subaru status"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
        assert any("subaru-talk-fast-path" in c for c in calls)
    finally:
        server.shutdown()


def test_status_alert_dry_run_exits_zero():
    proc = subprocess.run(
        ["bash", str(SCRIPTS / "subaru-status-alert.sh"), "--dry-run"],
        capture_output=True,
        text=True,
        env={**os.environ, "SUBARU_ENABLED": "1"},
        check=False,
    )
    assert proc.returncode == 0
    assert "SUBARU_ALERT_OK dry-run" in proc.stdout


def test_dispatch_exec_requires_talk_confirm():
    env = {
        "HOME": os.environ["HOME"],
        "PATH": os.environ["PATH"],
        "USER": os.environ.get("USER", ""),
        "OPENCLAW_AGENT_MENTION": "@openclaw",
        "SUBARU_TALK_FASTPATH": "1",
        "SUBARU_REQUIRE_TALK_CONFIRM": "1",
        "SUBARU_ACTUATION_ENABLED": "1",
        "SUBARU_FASTPATH_ACTUATION": "0",
    }
    proc = subprocess.run(
        ["bash", str(SCRIPTS / "subaru-dispatch-exec.sh"), "@openclaw subaru lock"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout.strip())
    assert payload.get("error_code") == "actuation_confirm_required"


def test_dispatch_exec_staleness_refresh_triggers_update(tmp_path):
    """Stale summary read should invoke update once before re-read."""
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    counter = script_dir / "vehicle_calls.txt"
    counter.write_text("0", encoding="utf-8")

    vehicle = script_dir / "subaru-vehicle.sh"
    vehicle.write_text(
        f"""#!/usr/bin/env bash
count_file="{counter}"
count=$(cat "$count_file")
echo $((count + 1)) > "$count_file"
if [[ "$*" == *update* ]]; then
  echo '{{}}' >&2
  exit 0
fi
if [[ "$count" -eq 0 ]]; then
  echo '{{"ok":true,"data":{{"meta":{{"staleness_seconds":999}}}}}}'
else
  echo '{{"ok":true,"data":{{"meta":{{"staleness_seconds":5}}}}}}'
fi
exit 0
""",
        encoding="utf-8",
    )
    vehicle.chmod(0o755)

    for name in ("subaru-dispatch-exec.sh", "subaru-dispatch.sh", "load-subaru-env.sh", "load-agent-env.sh"):
        src = SCRIPTS / name
        if src.is_file():
            (script_dir / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    lib_dst = script_dir / "lib"
    lib_dst.mkdir(exist_ok=True)
    for py in (LIB).glob("*.py"):
        (lib_dst / py.name).write_text(py.read_text(encoding="utf-8"), encoding="utf-8")

    openclaw = tmp_path / "openclaw"
    openclaw.mkdir()
    (openclaw / ".env").write_text("SUBARU_ENABLED=1\nOPENCLAW_AGENT_MENTION=@openclaw\n", encoding="utf-8")

    env = {
        **os.environ,
        "OPENCLAW_DIR": str(openclaw),
        "OPENCLAW_SUBARU_ROOT": str(ROOT),
        "SUBARU_TALK_FASTPATH": "1",
        "SUBARU_TALK_REFRESH_MAX_AGE_S": "300",
        "SUBARU_UPDATE_MIN_INTERVAL_S": "600",
        "SUBARU_ENABLED": "1",
        "OPENCLAW_AGENT_MENTION": "@openclaw",
        "SUBARU_PYTHON": "python3",
    }
    proc = subprocess.run(
        ["bash", str(script_dir / "subaru-dispatch-exec.sh"), "@openclaw subaru summary"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    calls = int(counter.read_text(encoding="utf-8").strip())
    assert calls >= 2, f"expected summary re-read after update, calls={calls}"
    payload = json.loads(proc.stdout.strip())
    assert payload["data"]["meta"]["staleness_seconds"] == 5


def test_talk_hooks_dispatch_builds_agent_wake_payload():
    sys_path = str(LIB)
    import sys

    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    from talk_hooks_dispatch import agent_id_for_room, strip_agent_mention

    assert agent_id_for_room("family-room", "family-room") == "family"
    assert agent_id_for_room("other", "family-room") == "main"
    assert strip_agent_mention("@openclaw what's up", "openclaw") == "what's up"


def test_fuel_doors_tires_aliases():
    sys_path = str(LIB)
    import sys

    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    from subaru_dispatch_parse import parse_dispatch

    assert parse_dispatch("@openclaw subaru fuel", "openclaw")["action"] == "condition"
    assert parse_dispatch("@openclaw subaru doors", "openclaw")["action"] == "condition"
    assert parse_dispatch("@openclaw subaru tires", "openclaw")["action"] == "health-report"


def test_fuel_digest_in_trips():
    import datetime as dt
    import sys

    if str(LIB) not in sys.path:
        sys.path.insert(0, str(LIB))
    from subaru_trips import fuel_digest

    now = dt.datetime.now(dt.timezone.utc)
    samples = [
        {"ts": (now - dt.timedelta(days=2)).isoformat(), "fuel_percent": 70},
        {"ts": now.isoformat(), "fuel_percent": 55},
    ]
    assert fuel_digest(samples, now=now) == "Fuel used last 7d: ~15%"
