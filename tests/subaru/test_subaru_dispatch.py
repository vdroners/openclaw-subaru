"""Dispatch fast-path parsing tests."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISPATCH = ROOT / "scripts" / "subaru-dispatch.sh"


def _run_dispatch(msg: str, mention: str = "@openclaw") -> dict:
    env = {**os.environ, "OPENCLAW_AGENT_MENTION": mention}
    proc = subprocess.run(
        ["bash", str(DISPATCH), msg],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    return json.loads(proc.stdout.strip())


def test_health_maps_to_health_report():
    payload = _run_dispatch("@openclaw subaru health")
    assert payload["action"] == "health-report"


def test_health_report_phrase():
    payload = _run_dispatch("@Openclaw subaru health-report")
    assert payload["action"] == "health-report"
    assert payload["args"] == []


def test_status_phrase_case_insensitive():
    payload = _run_dispatch("@OPENCLAW subaru status")
    assert payload["action"] == "status"


def test_status_without_at_mention():
    payload = _run_dispatch("Openclaw subaru status", mention="@openclaw")
    assert payload["action"] == "status"


def test_status_with_at_openclaw():
    payload = _run_dispatch("@openclaw subaru summary", mention="@openclaw")
    assert payload["action"] == "summary"


def test_mention_chip_agent_subaru_status():
    payload = _run_dispatch("{mention-user1} Openclaw subaru status", mention="@openclaw")
    assert payload["action"] == "status"


def test_mention_chip_subaru_only():
    payload = _run_dispatch("{mention-user1} subaru status", mention="@openclaw")
    assert payload["action"] == "status"
