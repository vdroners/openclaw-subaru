"""Odometer / fuel trip logging + weekly digest (no network).

A tiny append-only JSONL of ``{ts, odometer, fuel_percent}`` samples taken from
status reads. From it we can answer "how far did we drive this week?" and "how
much fuel did we burn?" without any extra API calls — the morning brief simply
appends one sample per day and renders a rolling digest.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_sample(status: dict[str, Any], now: datetime | None = None) -> dict[str, Any] | None:
    """Extract a trip sample from a vehicle_status dict, or None if no odometer."""
    if not isinstance(status, dict):
        return None
    odo = status.get("ODOMETER")
    if odo is None:
        return None
    try:
        odo_val = float(odo)
    except (TypeError, ValueError):
        return None
    sample: dict[str, Any] = {
        "ts": (now or utc_now()).isoformat(),
        "odometer": odo_val,
    }
    fuel = status.get("REMAINING_FUEL_PERCENT")
    if fuel is not None:
        try:
            sample["fuel_percent"] = float(fuel)
        except (TypeError, ValueError):
            pass
    return sample


def load_samples(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return out


def append_sample(
    path: str | Path,
    sample: dict[str, Any] | None,
    *,
    max_rows: int = 2000,
    dedupe_same_odometer: bool = True,
) -> bool:
    """Append a sample to the JSONL. Returns True if written.

    Skips writing when the odometer is unchanged from the most recent sample so a
    parked car polled repeatedly does not bloat the log.
    """
    if not sample:
        return False
    p = Path(path)
    existing = load_samples(p)
    if dedupe_same_odometer and existing:
        last = existing[-1]
        if last.get("odometer") == sample.get("odometer"):
            return False
    existing.append(sample)
    if len(existing) > max_rows:
        existing = existing[-max_rows:]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(s) for s in existing) + "\n", encoding="utf-8")
    return True


def _within(samples: list[dict[str, Any]], now: datetime, days: int) -> list[dict[str, Any]]:
    cutoff = now - timedelta(days=days)
    keep = []
    for s in samples:
        try:
            ts = datetime.fromisoformat(str(s.get("ts")).replace("Z", "+00:00")).astimezone(timezone.utc)
        except (ValueError, TypeError):
            continue
        if ts >= cutoff:
            keep.append({**s, "_ts": ts})
    return sorted(keep, key=lambda s: s["_ts"])


def weekly_digest(
    samples: list[dict[str, Any]], now: datetime | None = None, days: int = 7
) -> str | None:
    """One-line rolling digest, e.g. ``Driven this week: 142 mi``. None if no data."""
    now = now or utc_now()
    window = _within(samples, now, days)
    odos = [float(s["odometer"]) for s in window if s.get("odometer") is not None]
    if len(odos) < 2:
        return None
    miles = max(odos) - min(odos)
    if miles <= 0:
        return None
    return f"Driven last {days}d: {miles:.0f} mi"
