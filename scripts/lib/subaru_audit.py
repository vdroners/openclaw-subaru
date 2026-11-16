#!/usr/bin/env python3
"""Actuation audit rows for ``subaru-command-log.jsonl``.

Every row carries who asked (``sender``), where (``room`` token), how
(``source``: talk / cli / agent / cron) and the outcome. Context comes from
explicit arguments or, failing that, the environment:

    SUBARU_AUDIT_SENDER     else TALK_ACTOR_ID
    SUBARU_AUDIT_ROOM       else TALK_ROOM
    SUBARU_AUDIT_SOURCE     else "cli"
    SUBARU_AUDIT_MESSAGE_ID else TALK_MESSAGE_ID

Never writes secrets: no PIN, password, VIN or coordinates are accepted here.

CLI (used by subaru-dispatch-exec.sh for refusals that never reach the core):
    subaru_audit.py log --command start --result refused --error-code room_not_allowed
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ACTUATION_COMMANDS = frozenset(
    {"lock", "unlock", "start", "remote_start", "stop", "remote_stop", "horn", "lights", "charge"}
)
VALID_SOURCES = ("talk", "cli", "agent", "cron", "router")
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _clean(value: object, limit: int = 120) -> str:
    text = _CTRL_RE.sub("", str(value or "")).strip()
    return text[:limit]


def audit_context(
    sender: str | None = None,
    room: str | None = None,
    source: str | None = None,
    message_id: str | None = None,
) -> dict[str, str]:
    env = os.environ
    src = _clean(source or env.get("SUBARU_AUDIT_SOURCE") or "cli", 20).lower()
    if src not in VALID_SOURCES:
        src = "cli"
    return {
        "sender": _clean(sender or env.get("SUBARU_AUDIT_SENDER") or env.get("TALK_ACTOR_ID") or ""),
        "room": _clean(room or env.get("SUBARU_AUDIT_ROOM") or env.get("TALK_ROOM") or "", 64),
        "source": src,
        "message_id": _clean(message_id or env.get("SUBARU_AUDIT_MESSAGE_ID") or env.get("TALK_MESSAGE_ID") or "", 64),
    }


def audit_log_path() -> Path:
    override = os.environ.get("SUBARU_AUDIT_LOG", "").strip()
    if override:
        return Path(override)
    base = Path(os.environ.get("OPENCLAW_DIR") or (Path.home() / ".openclaw"))
    return base / "state" / "subaru-command-log.jsonl"


def build_row(
    command: str,
    *,
    ok: bool,
    result: str,
    error_code: str | None = None,
    tier: int | None = None,
    context: dict[str, str] | None = None,
    extra: dict | None = None,
) -> dict:
    ctx = context or audit_context()
    row: dict = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "command": _clean(command, 40),
        "ok": bool(ok),
        "result": result,  # ok | failed | refused
        "error_code": error_code,
        "rejected_reason": error_code if result == "refused" else None,
        **ctx,
    }
    if tier is not None:
        row["tier"] = tier
    if extra:
        for key, value in extra.items():
            if key.lower() in ("pin", "password", "vin", "latitude", "longitude", "lat", "lon"):
                continue
            row[key] = value
    return row


def write_row(row: dict, path: Path | None = None) -> Path:
    target = path or audit_log_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("log")
    lg.add_argument("--command", required=True)
    lg.add_argument("--result", choices=("ok", "failed", "refused"), required=True)
    lg.add_argument("--error-code", default=None)
    lg.add_argument("--sender")
    lg.add_argument("--room")
    lg.add_argument("--source")
    lg.add_argument("--message-id")
    lg.add_argument("--preset")
    lg.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args(argv)
    ctx = audit_context(ns.sender, ns.room, ns.source, ns.message_id)
    extra: dict = {}
    if ns.preset:
        extra["preset"] = _clean(ns.preset, 60)
    if ns.dry_run:
        extra["dry_run"] = True
    row = build_row(
        ns.command,
        ok=ns.result == "ok",
        result=ns.result,
        error_code=ns.error_code,
        context=ctx,
        extra=extra,
    )
    write_row(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
