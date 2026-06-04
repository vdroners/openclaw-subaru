---
name: subaru-vehicle
description: MySubaru Connected Services for the household Subaru (status, health, locate, lock, remote start).
metadata:
  openclaw:
    requires:
      env:
        - SUBARU_ENABLED
        - SUBARU_USERNAME
        - SUBARU_VIN
---

# Subaru vehicle (MySubaru / STARLINK)

Use **`scripts/subaru-vehicle.sh`** for all MySubaru operations. Requires active **Security Plus** subscription (US/Canada).

## Data freshness (use the lightest command that answers the question)

| Need | Command |
|------|---------|
| Cached fuel/odometer/TPMS | `subaru-vehicle.sh status` |
| Newer cloud cache | `subaru-vehicle.sh fetch` |
| Wake vehicle for fresh sensors | `subaru-vehicle.sh update` |
| GPS / "where is the car?" | `subaru-vehicle.sh locate` (max once per 2h) |

## Read-only (safe anytime)

```bash
subaru-vehicle.sh status
subaru-vehicle.sh summary
subaru-vehicle.sh health-report
subaru-vehicle.sh condition
subaru-vehicle.sh capabilities
subaru-vehicle.sh locate
subaru-vehicle.sh maps-link
subaru-vehicle.sh presets list
```

Target a specific vehicle with `subaru-vehicle.sh --vin <VIN> status`, or in Talk
say `@openclaw subaru <nickname> status` when `SUBARU_VEHICLE_ALIASES` maps the
nickname to a VIN.

## Actuation (requires `SUBARU_ACTUATION_ENABLED=1` + PIN on disk)

Confirm with the operator before Tier 3 commands (`unlock`, `start`).

```bash
subaru-vehicle.sh lock
subaru-vehicle.sh unlock [--door driver|tailgate|all]
subaru-vehicle.sh start --preset "PresetName"
subaru-vehicle.sh stop
subaru-vehicle.sh horn [--stop]
subaru-vehicle.sh lights [--stop]
```

Never echo PIN or password in Talk replies.

## Talk fast-path

Messages matching `@?openclaw subaru …` (with or without `@`) or `{mention-userN} subaru …` are handled by **`subaru-talk-fast-path.sh`** on the Talk webhook shim (**:8788**) — **no LLM**. The relay on :8789 has the same pattern as a secondary path.

```bash
bash ~/.openclaw/scripts/subaru-talk-fast-path.sh "<exact user message>" <room_token>
```

Parse-only: `subaru-dispatch.sh`. Dry-run exec: `subaru-dispatch-exec.sh --dry-run "…"`.

Example mentions: `status`, `health-report`, `locate`, `start [preset]`, `lock`, `unlock driver`.

## Proactive crons (optional)

- `subaru-status-alert.sh` — posts once on a new actionable condition (door open,
  unlocked, window down, low fuel/range/tire, ignition on) and dedupes repeats.
- `subaru-scheduled-start.sh` — scheduled remote start; gated by
  `SUBARU_SCHEDULED_START=1` + `SUBARU_ACTUATION_ENABLED=1`.
- Morning brief appends a rolling `Driven last 7d: N mi` trip digest.

## Out of scope

Live OBD2/DTC codes, service scheduling, Wi-Fi hotspot — not available via MySubaru API.
