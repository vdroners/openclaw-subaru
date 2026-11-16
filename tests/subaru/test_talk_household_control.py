"""Talk household control: multi-word presets, audit context, Family Hub room gate.

Nothing here touches MySubaru: dispatch-exec runs with --dry-run, the core runs
against a fake controller, and OPENCLAW_DIR points at a temp dir so the live
~/.openclaw/.env and audit log are never read or written.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS / "lib"))

from subaru_audit import audit_context, build_row  # noqa: E402
from subaru_dispatch_parse import parse_dispatch, parse_preset  # noqa: E402

KNOWN = ["Auto", "Full Cool", "Full Heat", "Dan Da Dan"]
ROOM_TOKEN = "famhubtest1"


# ---------------------------------------------------------------- preset parse
@pytest.mark.parametrize(
    "msg,preset",
    [
        ("@alfred subaru start Dan Da Dan", "Dan Da Dan"),
        ("@alfred subaru start Dan Da Dan confirm", "Dan Da Dan"),
        ('@alfred subaru start "Dan Da Dan"', "Dan Da Dan"),
        ("@alfred subaru start 'dan da dan' confirm", "Dan Da Dan"),
        ("@alfred subaru start \u201cDan Da Dan\u201d", "Dan Da Dan"),
        ("subaru start with full heat", "Full Heat"),
        ("subaru start using preset Full Cool please", "Full Cool"),
        ("subaru start the car with Dan Da Dan", "Dan Da Dan"),
        ("subaru start auto", "Auto"),
        ("subaru start Custom Thing", "Custom Thing"),  # unknown passes through
    ],
)
def test_multiword_preset(msg, preset):
    parsed = parse_dispatch(msg, "alfred", known_presets=KNOWN)
    assert parsed == {"action": "start", "args": ["--preset", preset]}


@pytest.mark.parametrize(
    "msg", ["subaru start", "subaru start confirm", "subaru start the car", "@alfred subaru start wolfram now"]
)
def test_start_without_preset_uses_default(msg):
    parsed = parse_dispatch(msg, "alfred", known_presets=KNOWN)
    assert parsed == {"action": "start", "args": []}


def test_parse_preset_never_returns_filler():
    assert parse_preset(["with"], KNOWN) == ""
    assert parse_preset(['"'], KNOWN) == ""


def test_unlock_door_parse_unchanged():
    assert parse_dispatch("subaru unlock driver", "alfred") == {"action": "unlock", "args": ["--door", "driver"]}


def test_vehicle_json_default_preset_is_known(tmp_path, monkeypatch):
    vj = tmp_path / "vehicle.json"
    vj.write_text(json.dumps({"remote_start_preset": "Dan Da Dan"}), encoding="utf-8")
    monkeypatch.setenv("SUBARU_VEHICLE_JSON", str(vj))
    assert parse_dispatch("subaru start dan da dan", "alfred") == {
        "action": "start",
        "args": ["--preset", "Dan Da Dan"],
    }


# ---------------------------------------------------------------- audit module
def test_audit_context_env_fallbacks(monkeypatch):
    for k in ("SUBARU_AUDIT_SENDER", "SUBARU_AUDIT_ROOM", "SUBARU_AUDIT_SOURCE", "SUBARU_AUDIT_MESSAGE_ID"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TALK_ACTOR_ID", "users/NCAdmin")
    monkeypatch.setenv("TALK_ROOM", ROOM_TOKEN)
    monkeypatch.setenv("TALK_MESSAGE_ID", "42")
    ctx = audit_context()
    assert ctx == {"sender": "users/NCAdmin", "room": ROOM_TOKEN, "source": "cli", "message_id": "42"}


def test_audit_context_sanitises(monkeypatch):
    ctx = audit_context(sender="users/a\nb\x00", source="bogus")
    assert ctx["sender"] == "users/ab"
    assert ctx["source"] == "cli"


def test_build_row_drops_secret_keys():
    row = build_row("start", ok=False, result="refused", error_code="x", context={}, extra={"pin": "1", "vin": "V", "preset": "Auto"})
    assert "pin" not in row and "vin" not in row
    assert row["preset"] == "Auto"
    assert row["rejected_reason"] == "x"


# ---------------------------------------------------------------- core audit
def _core_runner(tmp_path):
    sys.path.insert(0, str(Path(__file__).parent))
    from test_subaru_live_mock import _runner  # noqa: PLC0415

    return _runner(tmp_path)


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_core_audit_row_has_context(tmp_path, monkeypatch):
    monkeypatch.setenv("SUBARU_AUDIT_SENDER", "users/NCAdmin")
    monkeypatch.setenv("SUBARU_AUDIT_ROOM", ROOM_TOKEN)
    monkeypatch.setenv("SUBARU_AUDIT_SOURCE", "talk")
    runner = _core_runner(tmp_path)

    async def ok(command, args):
        return {"ok": True}

    runner._run_live = ok  # type: ignore[assignment]
    asyncio.run(runner.run("lock", {}))
    row = _rows(tmp_path / "audit.jsonl")[-1]
    assert row["command"] == "lock" and row["ok"] is True and row["result"] == "ok"
    assert row["sender"] == "users/NCAdmin" and row["room"] == ROOM_TOKEN and row["source"] == "talk"


def test_core_audits_failed_actuation(tmp_path):
    runner = _core_runner(tmp_path)

    async def boom(command, args):
        raise RuntimeError("preset_missing")

    runner._run_live = boom  # type: ignore[assignment]
    resp = asyncio.run(runner.run("start", {}))
    assert resp["error_code"] == "preset_missing"
    row = _rows(tmp_path / "audit.jsonl")[-1]
    assert row["command"] == "start" and row["result"] == "failed" and row["error_code"] == "preset_missing"


def test_core_audits_refused_actuation(tmp_path):
    runner = _core_runner(tmp_path)
    runner.settings.actuation_enabled = False
    asyncio.run(runner.run("unlock", {}))
    row = _rows(tmp_path / "audit.jsonl")[-1]
    assert row["result"] == "refused" and row["rejected_reason"] == "actuation_disabled"


# ---------------------------------------------------------------- dispatch-exec gates
def _exec(tmp_path: Path, *args: str, env_extra: dict | None = None) -> tuple[subprocess.CompletedProcess, list[dict]]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SUBARU_", "TALK_", "SKYLIGHT_"))
    }
    env.update(
        {
            "OPENCLAW_DIR": str(tmp_path),
            "SUBARU_ACTUATION_ENABLED": "1",
            "SKYLIGHT_FAMILY_TALK_ROOM": ROOM_TOKEN,
            "OPENCLAW_AGENT_MENTION": "@alfred",
        }
    )
    env.update(env_extra or {})
    proc = subprocess.run(
        ["bash", str(SCRIPTS / "subaru-dispatch-exec.sh"), "--dry-run", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    return proc, _rows(tmp_path / "state" / "subaru-command-log.jsonl")


def _fh(*extra: str) -> list[str]:
    return ["--source", "talk", "--verified", "valid", "--sender", "users/kid", "--room", ROOM_TOKEN, *extra]


def test_exec_family_hub_start_with_multiword_preset(tmp_path):
    proc, rows = _exec(tmp_path, *_fh("--allowed-room"), "subaru start Dan Da Dan")
    assert proc.returncode == 0
    assert "action=start" in proc.stdout and "Dan\\ Da\\ Dan" in proc.stdout
    assert rows == []  # allowed dry-runs are not real attempts


def test_exec_other_room_refused_and_audited(tmp_path):
    proc, rows = _exec(
        tmp_path, "--source", "talk", "--verified", "valid", "--sender", "users/x", "--room", "otherroom", "--allowed-room", "subaru unlock"
    )
    out = json.loads(proc.stdout)
    assert out["error_code"] == "room_not_allowed"
    assert ROOM_TOKEN not in proc.stdout + proc.stderr
    assert rows[-1]["result"] == "refused" and rows[-1]["room"] == "otherroom" and rows[-1]["sender"] == "users/x"


def test_exec_dm_without_room_refused(tmp_path):
    proc, rows = _exec(tmp_path, "--source", "talk", "--verified", "valid", "--sender", "users/x", "--allowed-room", "subaru start")
    assert json.loads(proc.stdout)["error_code"] == "room_not_allowed"
    assert rows[-1]["rejected_reason"] == "room_not_allowed"


def test_exec_unconfigured_room_fails_closed(tmp_path):
    proc, rows = _exec(tmp_path, *_fh("--allowed-room"), "subaru lock", env_extra={"SKYLIGHT_FAMILY_TALK_ROOM": ""})
    assert json.loads(proc.stdout)["error_code"] == "allowed_room_unconfigured"
    assert rows[-1]["result"] == "refused"


def test_exec_custom_room_var(tmp_path):
    env = {"SUBARU_ALLOWED_ROOM_VAR": "MY_ROOM", "MY_ROOM": "abc"}
    proc, _ = _exec(tmp_path, *_fh("--allowed-room"), "subaru lock", env_extra=env)
    assert json.loads(proc.stdout)["error_code"] == "room_not_allowed"
    proc, _ = _exec(tmp_path, "--source", "talk", "--verified", "valid", "--sender", "u", "--room", "abc", "--allowed-room", "subaru lock", env_extra=env)
    assert "action=lock" in proc.stdout


def test_exec_unverified_talk_refused(tmp_path):
    proc, rows = _exec(tmp_path, "--source", "talk", "--sender", "users/x", "--room", ROOM_TOKEN, "--allowed-room", "subaru start")
    assert json.loads(proc.stdout)["error_code"] == "talk_unverified"
    assert rows[-1]["rejected_reason"] == "talk_unverified"


def test_exec_env_enforcement_and_env_context(tmp_path):
    env = {
        "SUBARU_ENFORCE_ALLOWED_ROOM": "1",
        "TALK_ACTOR_ID": "users/envuser",
        "TALK_ROOM": "elsewhere",
        "TALK_VERIFIED": "valid",
        "SUBARU_AUDIT_SOURCE": "talk",
    }
    proc, rows = _exec(tmp_path, "subaru horn", env_extra=env)
    assert json.loads(proc.stdout)["error_code"] == "room_not_allowed"
    assert rows[-1]["sender"] == "users/envuser" and rows[-1]["room"] == "elsewhere" and rows[-1]["source"] == "talk"


def test_exec_reads_not_room_gated(tmp_path):
    proc, rows = _exec(tmp_path, "--room", "otherroom", "--allowed-room", "subaru status")
    assert "action=status" in proc.stdout
    assert rows == []


def test_exec_actuation_disabled_is_audited(tmp_path):
    proc, rows = _exec(tmp_path, *_fh(), "subaru start", env_extra={"SUBARU_ACTUATION_ENABLED": "0"})
    assert json.loads(proc.stdout)["error_code"] == "actuation_disabled"
    assert rows[-1]["command"] == "start" and rows[-1]["result"] == "refused"


def test_exec_confirm_gate_text_uses_mention(tmp_path):
    env = {"SUBARU_TALK_FASTPATH": "1", "SUBARU_REQUIRE_TALK_CONFIRM": "1"}
    proc, rows = _exec(tmp_path, *_fh(), "subaru start", env_extra=env)
    out = json.loads(proc.stdout)
    assert out["error_code"] == "actuation_confirm_required"
    assert "@alfred subaru start confirm" in out["errors"][0]
    assert "@openclaw" not in proc.stdout
    assert rows[-1]["rejected_reason"] == "actuation_confirm_required"


def test_exec_unknown_option_is_usage_error(tmp_path):
    proc, _ = _exec(tmp_path, "--bogus", "subaru status")
    assert proc.returncode == 2
