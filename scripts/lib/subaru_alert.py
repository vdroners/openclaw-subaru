"""Alert dedup helpers for subaru-status-alert.sh and tests."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _severity_rank(verdict: str) -> int:
    v = (verdict or "pass").lower()
    if v == "fail":
        return 2
    if v == "warn":
        return 1
    return 0


def should_post_alert(
    state: dict[str, Any],
    *,
    verdict: str,
    score: int | float,
    prev_verdict: str,
    prev_score: int | float,
    min_interval_h: float,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Return (should_post, reason)."""
    now = now or datetime.now(timezone.utc)
    posted = state.get("last_post_ts")
    if not posted:
        return True, "no_prior_post"
    try:
        ts = datetime.fromisoformat(str(posted).replace("Z", "+00:00"))
    except ValueError:
        return True, "unreadable_last_post_ts"
    age_h = (now - ts.astimezone(timezone.utc)).total_seconds() / 3600.0
    if age_h >= min_interval_h:
        return True, f"interval_ok_{age_h:.1f}h"
    cur_rank = _severity_rank(verdict)
    prev_rank = _severity_rank(prev_verdict)
    if cur_rank > prev_rank:
        return True, "severity_escalation"
    try:
        if float(prev_score) - float(score) >= 10:
            return True, "score_drop"
    except (TypeError, ValueError):
        pass
    return False, f"dedup_{age_h:.1f}h"
