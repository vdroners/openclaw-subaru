#!/usr/bin/env python3
"""Print the first JSON object found in stdin text (e.g. a CLI's stderr).

subaru-vehicle.sh writes the failure envelope to stderr followed by
"SUBARU_ERR command failed"; this pulls the envelope back out. Exit 1 if none.
"""

from __future__ import annotations

import json
import sys


def extract(text: str) -> dict | None:
    dec = json.JSONDecoder()
    i = text.find("{")
    while i != -1:
        try:
            obj, _ = dec.raw_decode(text, i)
        except ValueError:
            i = text.find("{", i + 1)
            continue
        if isinstance(obj, dict):
            return obj
        i = text.find("{", i + 1)
    return None


def main() -> int:
    obj = extract(sys.stdin.read())
    if obj is None:
        return 1
    print(json.dumps(obj))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
