#!/usr/bin/env python3
"""CLI entry for MySubaru OpenClaw integration."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LIB = SCRIPT_DIR / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from subaru_core import main as core_main, run_command, print_json, validate_response_envelope  # noqa: E402


COMMAND_MAP = {
    "status": "status",
    "summary": "summary",
    "raw": "raw",
    "show": "show",
    "fetch": "fetch",
    "update": "update",
    "locate": "locate",
    "capabilities": "capabilities",
    "health": "health",
    "condition": "condition",
    "health-report": "health-report",
    "maps-link": "maps-link",
    "lock": "lock",
    "unlock": "unlock",
    "start": "start",
    "remote_start": "start",
    "stop": "stop",
    "remote_stop": "stop",
    "horn": "horn",
    "lights": "lights",
    "charge": "charge",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="OpenClaw Subaru / MySubaru CLI")
    p.add_argument("--dry-run", action="store_true", help="No network; fixture responses")
    p.add_argument("--bridge", action="store_true", help="Route via SUBARU_BRIDGE_URL HTTP client")
    sub = p.add_subparsers(dest="command", required=True)

    for name in (
        "status",
        "summary",
        "raw",
        "show",
        "fetch",
        "update",
        "capabilities",
        "health",
        "condition",
        "maps-link",
        "lock",
        "stop",
        "remote_stop",
        "charge",
    ):
        sub.add_parser(name)

    sp = sub.add_parser("start")
    sp.add_argument("--preset")
    sp.add_argument("preset_positional", nargs="?", default=None)
    sp = sub.add_parser("remote_start")
    sp.add_argument("--preset")
    sp.add_argument("preset_positional", nargs="?", default=None)
    sp = sub.add_parser("unlock")
    sp.add_argument("--door", choices=["all", "driver", "drivers", "tailgate"], default="all")

    sp = sub.add_parser("horn")
    sp.add_argument("--stop", action="store_true")
    sp = sub.add_parser("lights")
    sp.add_argument("--stop", action="store_true")

    sp = sub.add_parser("locate")
    sp.add_argument("--force", action="store_true")

    sp = sub.add_parser("health-report")
    sp.add_argument("--prefetch", action="store_true")

    auth = sub.add_parser("auth")
    auth_sub = auth.add_subparsers(dest="auth_cmd", required=True)
    auth_sub.add_parser("connect")
    auth_sub.add_parser("check")

    pin = sub.add_parser("pin")
    pin_sub = pin.add_subparsers(dest="pin_cmd", required=True)
    pin_sub.add_parser("test")

    presets = sub.add_parser("presets")
    presets_sub = presets.add_subparsers(dest="presets_cmd", required=True)
    presets_sub.add_parser("list")
    presets_sub.add_parser("show")
    pg = presets_sub.add_parser("get")
    pg.add_argument("name")
    pd = presets_sub.add_parser("default")
    pd.add_argument("name")
    pdel = presets_sub.add_parser("delete")
    pdel.add_argument("name")
    padd = presets_sub.add_parser("add")
    padd.add_argument("--file", required=True)

    vehicles = sub.add_parser("vehicles")
    vehicles_sub = vehicles.add_subparsers(dest="vehicles_cmd", required=True)
    vehicles_sub.add_parser("list")
    vs = vehicles_sub.add_parser("select")
    vs.add_argument("vin")

    cfg = sub.add_parser("config")
    cfg_sub = cfg.add_subparsers(dest="config_cmd", required=True)
    cs = cfg_sub.add_parser("set")
    cs.add_argument("key")
    cs.add_argument("value", type=int)

    sub.add_parser("validate-response")
    return p


def resolve_command(ns: argparse.Namespace) -> tuple[str, dict]:
    cmd = ns.command
    args: dict = {}
    if cmd == "auth":
        return f"auth-{ns.auth_cmd}", args
    if cmd == "pin":
        return "pin-test", args
    if cmd == "presets":
        mapping = {
            "list": "presets-list",
            "show": "presets-show",
            "get": "presets-get",
            "default": "presets-default",
            "delete": "presets-delete",
            "add": "presets-add",
        }
        inner = mapping[ns.presets_cmd]
        if ns.presets_cmd == "get":
            args["name"] = ns.name
        elif ns.presets_cmd == "default":
            args["name"] = ns.name
        elif ns.presets_cmd == "delete":
            args["name"] = ns.name
        elif ns.presets_cmd == "add":
            args["preset_file"] = ns.file
        return inner, args
    if cmd == "vehicles":
        if ns.vehicles_cmd == "list":
            return "vehicles-list", args
        return "vehicles-select", {"vin": ns.vin}
    if cmd == "config":
        return "config-set", {"key": ns.key, "value": ns.value}

    inner = COMMAND_MAP.get(cmd, cmd)
    if cmd == "unlock":
        args["door"] = ns.door
    if cmd in ("horn", "lights") and getattr(ns, "stop", False):
        args["stop"] = True
    if cmd == "locate" and getattr(ns, "force", False):
        args["force"] = True
    if cmd == "health-report" and getattr(ns, "prefetch", False):
        args["prefetch"] = True
    if cmd in ("start", "remote_start"):
        preset = getattr(ns, "preset", None) or getattr(ns, "preset_positional", None)
        if preset:
            args["preset"] = preset
    return inner, args


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] == "--help":
        build_parser().print_help()
        return 0
    # Legacy passthrough: subaru_cli.py status --dry-run
    if argv and argv[0] in COMMAND_MAP and "--dry-run" in argv:
        dry = True
        rest = [a for a in argv if a != "--dry-run"]
        payload = run_command(COMMAND_MAP.get(rest[0], rest[0]), {}, dry_run=dry)
        print_json(payload)
        return 0 if payload.get("ok") else 1

    parser = build_parser()
    ns = parser.parse_args(argv)
    if ns.command == "validate-response":
        import json

        data = json.load(sys.stdin)
        errs = validate_response_envelope(data)
        if errs:
            print("\n".join(errs), file=sys.stderr)
            return 1
        print("validate-response: ok")
        return 0

    inner, args = resolve_command(ns)
    use_bridge = (
        not ns.dry_run
        and os.environ.get("SUBARU_BRIDGE_URL")
        and (getattr(ns, "bridge", False) or os.environ.get("SUBARU_USE_BRIDGE", "") == "1")
    )
    if use_bridge:
        from subaru_bridge_client import run_bridge_command  # noqa: E402

        payload = run_bridge_command(os.environ["SUBARU_BRIDGE_URL"], inner, args)
        print_json(payload)
        return 0 if payload.get("ok") else 1
    payload = run_command(inner, args, dry_run=ns.dry_run)
    print_json(payload)
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
