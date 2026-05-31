#!/usr/bin/env python3
"""Submit MySubaru 2FA device registration code (one shot)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parent
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from subaru_core import Settings  # noqa: E402
from subaru_health import exception_to_error_code  # noqa: E402


async def _register(code: str, *, request_first: bool) -> int:
    import aiohttp
    from subarulink import Controller
    from subarulink import const as sc

    s = Settings(dry_run=False)
    session = aiohttp.ClientSession()
    try:
        ctrl = Controller(
            session,
            s.username,
            s.password,
            s.device_id,
            s.pin,
            s.device_name,
            country=sc.COUNTRY_USA,
        )
        try:
            await ctrl.connect()
        except Exception as exc:
            code_name = exception_to_error_code(exc)
            print(f"SUBARU_2FA_FAIL connect: {code_name} ({exc})", file=sys.stderr)
            return 1

        if ctrl.device_registered:
            print("SUBARU_2FA_OK already registered")
            return 0

        if request_first:
            methods = dict(getattr(ctrl, "contact_methods", {}) or {})
            if not methods:
                methods = dict(getattr(ctrl._connection, "auth_contact_methods", {}) or {})
            if not methods:
                print("SUBARU_2FA_FAIL no contact methods on account", file=sys.stderr)
                return 1
            contact = os.environ.get("SUBARU_2FA_CONTACT", "EMAIL")
            if contact not in methods:
                contact = next(iter(methods.keys()))
            print(f"SUBARU_2FA_REQUEST sending code via {contact} ({methods.get(contact, contact)})")
            if not await ctrl.request_auth_code(contact):
                print("SUBARU_2FA_FAIL request_auth_code failed (account locked?)", file=sys.stderr)
                return 1
            if not code:
                prompt = os.environ.get("SUBARU_DEVICE_REGISTER_CODE", "").strip()
                if not prompt:
                    try:
                        prompt = input("Enter 6-digit verification code: ").strip()
                    except EOFError:
                        prompt = ""
                code = prompt

        if len(code) != 6 or not code.isdecimal():
            print("SUBARU_2FA_FAIL invalid code (need 6 digits)", file=sys.stderr)
            return 2

        ok = await ctrl.submit_auth_code(code)
        if ok and ctrl.device_registered:
            print("SUBARU_2FA_OK device registered")
            return 0
        print("SUBARU_2FA_FAIL submit failed (wrong/expired code or account locked)")
        return 1
    finally:
        await session.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="One-shot MySubaru 2FA device registration")
    parser.add_argument("code", nargs="?", default="", help="6-digit verification code")
    parser.add_argument(
        "--request",
        action="store_true",
        help="Request email/SMS code in this session, then submit (prompts if code omitted)",
    )
    args = parser.parse_args()
    code = (args.code or os.environ.get("SUBARU_DEVICE_REGISTER_CODE", "")).strip()
    return asyncio.run(_register(code, request_first=args.request))


if __name__ == "__main__":
    raise SystemExit(main())
