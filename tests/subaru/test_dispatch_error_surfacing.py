"""dispatch-exec must surface the real CLI error instead of "cli_no_output".

subaru-vehicle.sh is replaced by a stub in a temp copy of scripts/, HOME and
OPENCLAW_DIR point at tmp_path, so nothing here reads the live .env or talks
to MySubaru.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS / "lib"))

from subaru_dispatch_parse import parse_dispatch  # noqa: E402
from subaru_format_talk_reply import format_talk_reply  # noqa: E402
from subaru_json_from_text import extract  # noqa: E402

ROOM = "famhubtest1"

FAIL_STUB = r"""#!/usr/bin/env bash
# Mimics subaru-vehicle.sh on a failed command: payload on STDERR, exit 1.
echo "$*" >> "${STUB_CALLS}"
cat >&2 <<'J'
{
  "ok": false,
  "command": "lock",
  "nickname": "Wolfram",
  "data": {},
  "errors": ["RemoteServiceFailure: Remote service request completed but failed: VEHICLE_DOOR_OPEN"],
  "error_code": "subaru_api"
}
J
echo "SUBARU_ERR command failed" >&2
exit 1
"""

SILENT_STUB = r"""#!/usr/bin/env bash
echo "$*" >> "${STUB_CALLS}"
echo "Traceback (most recent call last): boom" >&2
exit 1
"""

STALE_STUB = r"""#!/usr/bin/env bash
# summary -> stale payload; update -> ok/throttled/fail per STUB_UPDATE.
echo "$*" >> "${STUB_CALLS}"
cmd="${@: -1}"
if [[ "$cmd" == "update" ]]; then
  case "${STUB_UPDATE:-ok}" in
    ok) echo '{"ok": true, "command": "update", "data": {"updated": true}}' ;;
    throttled) echo '{"ok": true, "command": "update", "data": {"updated": false, "throttled": true}}' ;;
    fail) echo '{"ok": false, "command": "update", "errors": ["x"], "error_code": "subaru_api"}' >&2; exit 1 ;;
  esac
  exit 0
fi
n=$(grep -c . "${STUB_CALLS}")
age=14400; [[ "$n" -ge 3 ]] && age=5
echo "{\"ok\": true, \"command\": \"$cmd\", \"nickname\": \"Wolfram\", \"data\": {\"vehicle_status\": {\"ODOMETER\": 1, \"staleness_seconds\": $age}, \"meta\": {\"staleness_seconds\": $age}}}"
"""


def _tree(tmp_path: Path, stub: str) -> Path:
    sd = tmp_path / "scripts"
    sd.mkdir()
    for name in ("subaru-dispatch-exec.sh", "subaru-dispatch.sh", "load-subaru-env.sh", "load-agent-env.sh"):
        shutil.copy2(SCRIPTS / name, sd / name)
    shutil.copytree(SCRIPTS / "lib", sd / "lib", ignore=shutil.ignore_patterns("__pycache__"))
    (sd / "subaru-vehicle.sh").write_text(stub, encoding="utf-8")
    (tmp_path / "state").mkdir()
    return sd


def _run(tmp_path: Path, stub: str, msg: str, extra_env: dict | None = None, *flags: str):
    sd = _tree(tmp_path, stub)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SUBARU_", "TALK_", "SKYLIGHT_", "HOUSEHOLD_"))}
    env.update(
        {
            "HOME": str(tmp_path),
            "OPENCLAW_DIR": str(tmp_path),
            "SUBARU_ACTUATION_ENABLED": "1",
            "SKYLIGHT_FAMILY_TALK_ROOM": ROOM,
            "OPENCLAW_AGENT_MENTION": "@familybot",
            "STUB_CALLS": str(tmp_path / "calls.txt"),
        }
    )
    env.update(extra_env or {})
    proc = subprocess.run(
        ["bash", str(sd / "subaru-dispatch-exec.sh"), *flags, msg],
        capture_output=True, text=True, env=env, check=False, timeout=60,
    )
    log = tmp_path / "state" / "subaru-command-log.jsonl"
    rows = [json.loads(x) for x in log.read_text().splitlines() if x.strip()] if log.is_file() else []
    calls = (tmp_path / "calls.txt").read_text().split("\n") if (tmp_path / "calls.txt").is_file() else []
    return proc, rows, [c for c in calls if c]


FH = ["--source", "talk", "--verified", "valid", "--sender", "users/NCAdmin", "--room", ROOM, "--allowed-room"]


def test_failed_lock_returns_real_error_json(tmp_path):
    proc, rows, calls = _run(tmp_path, FAIL_STUB, "subaru lock", None, *FH)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False and payload["error_code"] == "subaru_api"
    assert "VEHICLE_DOOR_OPEN" in payload["errors"][0]
    assert "cli rc=1" in proc.stderr
    # No wrapper-level cli_no_output row: the core audits the real failure itself.
    assert not any(r.get("error_code") == "cli_no_output" for r in rows)
    assert len(calls) == 1  # never retried


def test_failed_lock_formats_for_talk(tmp_path):
    proc, _, _ = _run(tmp_path, FAIL_STUB, "subaru lock", None, *FH)
    text = format_talk_reply(json.loads(proc.stdout))
    assert "subaru_api" in text and "VEHICLE_DOOR_OPEN" in text


def test_silent_cli_still_audits_cli_no_output(tmp_path):
    proc, rows, _ = _run(tmp_path, SILENT_STUB, "subaru lock", None, *FH)
    assert proc.returncode == 1
    assert proc.stdout.strip() == ""
    assert "no JSON from subaru-vehicle.sh (rc=1)" in proc.stderr
    assert "Traceback" in proc.stderr
    assert rows and rows[-1]["error_code"] == "cli_no_output"


@pytest.mark.parametrize(
    "mode,expect_refresh,fresh",
    [("ok", None, True), ("throttled", "throttled", False), ("fail", "failed", False)],
)
def test_stale_read_refresh_states(tmp_path, mode, expect_refresh, fresh):
    env = {"SUBARU_TALK_FASTPATH": "1", "STUB_UPDATE": mode}
    proc, _, calls = _run(tmp_path, STALE_STUB, "subaru summary", env)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    meta = payload["data"]["meta"]
    assert meta.get("refresh") == expect_refresh
    assert (meta["staleness_seconds"] < 300) is fresh
    assert sum(1 for c in calls if c.endswith("update")) == 1  # one wake-up at most


def test_extract_json_from_stderr_text():
    assert extract('noise\n{"ok": false, "a": {"b": 1}}\nSUBARU_ERR command failed\n') == {"ok": False, "a": {"b": 1}}
    assert extract("no json here") is None


@pytest.mark.parametrize("msg", ["subaru update", "subaru refresh", "@openclaw subaru refresh"])
def test_parse_update_refresh(msg):
    assert parse_dispatch(msg, "openclaw") == {"action": "update", "args": []}


@pytest.mark.parametrize(
    "refresh,needle",
    [(None, 'say "refresh the car"'), ("failed", "a fresh reading failed"), ("throttled", "asked recently")],
)
def test_stale_wording(monkeypatch, refresh, needle):
    monkeypatch.delenv("SUBARU_TALK_REFRESH_MAX_AGE_S", raising=False)
    meta = {"staleness_seconds": 4 * 3600}
    if refresh:
        meta["refresh"] = refresh
    text = format_talk_reply({"ok": True, "command": "summary", "nickname": "Wolfram",
                              "data": {"vehicle_status": {"ODOMETER": 1}, "meta": meta}})
    assert "last report from the car ~4h ago" in text and needle in text
    assert "could not refresh" not in text


def test_core_audits_library_exception_for_actuation(tmp_path):
    sys.path.insert(0, str(Path(__file__).parent))
    from test_talk_household_control import _core_runner, _rows  # noqa: PLC0415

    runner = _core_runner(tmp_path)

    class RemoteServiceFailure(Exception):
        pass

    async def boom(command, args):
        raise RemoteServiceFailure("Remote service request completed but failed: X")

    runner._run_live = boom  # type: ignore[assignment]
    resp = asyncio.run(runner.run("lock", {}))
    assert resp["ok"] is False
    assert resp["errors"][0].startswith("RemoteServiceFailure: Remote service request completed but failed")
    row = _rows(tmp_path / "audit.jsonl")[-1]
    assert row["command"] == "lock" and row["result"] == "failed"
