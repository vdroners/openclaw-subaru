# Subaru OpenClaw integration (v3)

Checked-in operator/engineering plan for **openclaw-subaru**. Mirrors the v3 integration scope: full `subarulink` command surface, health scorecard, gated actuation, Talk fast-path, cron alerts, optional REST bridge, and three-tier pass/fail gates.

## Architecture

- **Phase 1:** `scripts/lib/subaru_core.py` + bash facade + OpenClaw skill
- **Phase 2:** `services/subaru-bridge/` loopback REST on `:8790`
- **Install target:** `~/.openclaw` via `scripts/install-to-openclaw.sh` (`OPENCLAW_SUBARU_ROOT`)

## Data freshness ladder

| Level | Command | Wakes vehicle? |
|-------|---------|----------------|
| 0 | `status` | No |
| 1 | `fetch` | No |
| 2 | `update` | Yes |
| 3 | `locate` | Yes (rate limited) |

Cron rule: `subaru-status-alert.sh` uses `fetch` + `health-report` only — never `locate`.

## Command IDs (summary)

- **R01–R18:** read-only queries (status, summary, raw, show, fetch, update, locate, capabilities, health, condition, health-report, maps-link, presets*, vehicles*)
- **A01–A07:** auth/session/PIN (connect, check, bootstrap, pin test)
- **C01–C11:** actuation (lock, unlock, start, stop, horn, lights, charge)
- **P01–P05:** climate preset management
- **E01–E03:** operator tuning (fetch/update intervals, locate rate state)

Out of scope: charge stop, SOS, OBD2/DTC text, service scheduling, Wi-Fi hotspot.

## Feature → gate traceability (excerpt)

| Feature | Gate(s) |
|---------|---------|
| R* dry-run | SUB-CLI-DRY, SUB-SMOKE |
| R* live | SUB-STATUS, SUB-FETCH, SUB-SUMMARY, … |
| Health scorecard | SUB-HEALTH, H-* checks in pytest |
| Actuation kill switch | SUB-BLOCK-ACT, SUB-ACT-PASS-FILE |
| Talk fast-path | SUB-DISPATCH |
| Cron alert | SUB-ALERT-DRY, CAP-SUB, SUB-CRON-DEDUP |
| Bridge | SUB-BRIDGE-* |
| Tier 3 manual | SUB-LIVE-* via `subaru-record-live-pass.sh` |

Full gate tables: [GATES.md](../GATES.md).

## Verification order

1. `make publish` — Tier 0
2. `make gates` — Tier 1 (live reads when `SUBARU_ENABLED=1`)
3. `bash scripts/subaru-gates.sh --check --live` — Tier 2
4. `bash scripts/subaru-record-live-pass.sh` — Tier 3
5. `make shell-cron` + optional `make bridge-gates`

## Related repos

- [openclaw-skylight](https://github.com/vdroners/openclaw-skylight) — Talk post + optional morning brief hook (`SUBARU_MORNING_BRIEF=1`)
