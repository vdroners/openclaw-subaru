"""Proactive condition-transition detection for subaru-status-alert.sh.

The health scorecard (``subaru_health.evaluate_health``) already classifies the
actionable conditions (door open, unlocked, window down, low fuel/range, tire
pressure, ignition left on, EV SOC, MIL). The status-alert cron historically
only posted on a *verdict* change or a score drop, so a brand-new condition that
appeared at the same severity rank as an existing one (e.g. a door opening while
fuel was already low) could be silently deduped.

This module derives a stable *condition signature* from the scorecard checks and
reports which conditions are newly active vs the previous run, so the alert cron
can post once per transition and stay quiet on repeats. No network, no I/O.
"""

from __future__ import annotations

from typing import Any, Iterable

# Scorecard check ids that represent an actionable, operator-facing condition.
# H-STALE / H-SUB / H-RES are intentionally excluded: staleness and subscription
# state are not "the car needs attention right now" transitions.
ALERTABLE_IDS = frozenset(
    {
        "H-DOOR",
        "H-LOCK",
        "H-WINDOW",
        "H-SUNROOF",
        "H-FUEL-PCT",
        "H-FUEL-RNG",
        "H-TPMS-LOW",
        "H-TPMS-HIGH",
        "H-IGNITION",
        "H-EV-SOC",
        "H-MIL",
    }
)


def condition_signature(checks: Iterable[dict[str, Any]]) -> list[str]:
    """Stable, sorted list of ``"id|message"`` for actionable warn/fail checks.

    The message is included so distinct instances of the same check id (e.g. two
    different doors open) are tracked independently.
    """
    sig: set[str] = set()
    for c in checks or []:
        cid = str(c.get("id") or "")
        status = str(c.get("status") or "").lower()
        if cid in ALERTABLE_IDS and status in ("warn", "fail"):
            sig.add(f"{cid}|{c.get('message') or ''}")
    return sorted(sig)


def new_conditions(prev_sig: Iterable[str], cur_sig: Iterable[str]) -> list[str]:
    """Conditions present now that were not present in the previous run."""
    prev = set(prev_sig or [])
    return [s for s in (cur_sig or []) if s not in prev]


def cleared_conditions(prev_sig: Iterable[str], cur_sig: Iterable[str]) -> list[str]:
    """Conditions that were present before and are no longer active."""
    cur = set(cur_sig or [])
    return [s for s in (prev_sig or []) if s not in cur]


def messages_for(signature: Iterable[str]) -> list[str]:
    """Human-readable messages (the right-hand side of ``id|message``)."""
    out = []
    for item in signature or []:
        _, _, msg = str(item).partition("|")
        out.append(msg or item)
    return out


def should_post_conditions(
    prev_sig: Iterable[str], cur_sig: Iterable[str]
) -> tuple[bool, list[str], str]:
    """Return (should_post, new_condition_messages, reason).

    Posts when a new actionable condition has appeared since the last run. Repeats
    of the same condition set are suppressed (the caller persists ``cur_sig``).
    """
    appeared = new_conditions(prev_sig, cur_sig)
    if appeared:
        return True, messages_for(appeared), "condition_change"
    return False, [], "no_new_conditions"
