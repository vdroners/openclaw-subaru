# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Shared Talk hooks dispatch helper (`scripts/lib/talk_hooks_dispatch.py`) used by
  the webhook shim to wake OpenClaw via `/hooks/agent` (family vs main by room).
- Integration tests for Talk shim fast-path + hooks dispatch room routing.

### Changed

- Family Hub room token is env-only (`SKYLIGHT_FAMILY_TALK_ROOM`); no hardcoded
  default room id in the shim or hooks dispatch.
- Talk mention examples and confirm prompts standardize on `@openclaw`.

## [1.1.0] - 2026-06-03

Reliability + feature expansion on top of the public 1.0.0 base. All new behavior
is offline/dry-run gated; `make publish` stays green with no credentials.

### Added

- Proactive condition-transition alerts (`scripts/lib/subaru_conditions.py`): the
  status-alert cron now posts once when a door opens, the car is left unlocked, a
  window/sunroof is down, fuel/range crosses a threshold, a tire goes low/high,
  ignition is left on, or a MIL appears — and dedupes repeats via a stored
  condition signature.
- Scheduled remote-start cron wrapper (`scripts/subaru-scheduled-start.sh`) with
  enable + actuation gates, weekday filter, preset resolution, and Talk confirm.
- Trip logging + rolling weekly digest (`scripts/lib/subaru_trips.py`): the morning
  brief records one odometer/fuel sample per day and appends `Driven last 7d: N mi`.
- Multi-vehicle support: `--vin` per command on `subaru_cli.py`, `subaru <nickname>`
  dispatch via `SUBARU_VEHICLE_ALIASES`, and bridge VIN routing through `/command`.
- Offline-safe reverse geocoding (`scripts/lib/subaru_geocode.py`, opt-in
  `SUBARU_GEOCODE=1`) so Talk location replies can show a place name (cached).
- New offline gate suite `scripts/subaru-feature-gates.sh` (SUB-RAW-REDACT,
  SUB-BRIDGE-MAPS, SUB-SHIM-BIND, SUB-UPDATE-THROTTLE, SUB-ALERT-TRANSITION,
  SUB-SCHED-START-DRY, SUB-TRIPLOG, SUB-VIN-ARG, SUB-GEOCODE) wired into
  `make publish` and a new `make feature-gates` target.
- pytest suite expanded to 100+ cases: conditions, trips, geocode, multi-vehicle,
  raw redaction + update throttle, Talk shim, device-register, FastAPI bridge app,
  and mocked `_run_live` status/update/throttle/error-mapping.

### Changed

- `talk-webhook-shim.py` now binds loopback (`127.0.0.1`) by default; LAN exposure
  is opt-in via `TALK_SHIM_LAN=1` (or explicit `TALK_SHIM_HOST`).
- Talk staleness auto-refresh coalesces via a global update/fetch throttle
  (`SUBARU_UPDATE_MIN_INTERVAL_S`) so rate-limited updates no longer re-hammer the
  MySubaru endpoint on every poll.
- Bridge container mounts vehicle config (read-only) + shared `state/` (read-write)
  so locate/update rate limits and the audit log match the host CLI; the bridge
  app resolves its lib path robustly for both repo and container layouts.
- CI hardened: pin Python 3.11, `pip install -r requirements.txt`, and a dedicated
  pytest job in addition to `make publish`.

### Fixed

- `subaru_core._redact_raw()` now actually redacts secret-bearing keys (token,
  session, pin, password, auth, ...) at every depth before `raw` leaves the process
  over the CLI or bridge (previously a no-op).
- Bridge client `maps-link` routed to `/status`; it now uses a dedicated
  `/maps-link` route, and the dead duplicate `READ_ROUTES` branch was removed.
- Bridge API-key check uses `secrets.compare_digest` (constant-time).
- `RuntimeError("unsupported")` (non-EV charge, unsupported vehicle) now surfaces
  as `error_code: unsupported` instead of the generic `subaru_api`.

## [1.0.0] - 2026-05-31

Public release — MySubaru integration for OpenClaw with gated actuation and Talk fast-path.

### Added

- Talk fast-path: `subaru-talk-fast-path.sh`, `talk-webhook-shim.py`, mention-chip + tool-JSON handling
- Shared parsers: `scripts/lib/subaru_talk_match.py`, `subaru_dispatch_parse.py`
- Device registration: `subaru-device-register.sh` with `--request` one-shot 2FA flow
- Talk formatter: `subaru-format-talk-reply.sh` + `subaru_format_talk_reply.py`
- Phase 2 bridge client, alert dedup, pass-file validation, expanded gate matrix
- pytest suite (50+ cases): core, health, dispatch, talk match, bridge, alert, formatter

### Changed

- Standardized agent branding on `@openclaw` (scrub gate rejects legacy operator aliases)
- `install-to-openclaw.sh` symlinks `scripts/lib/` and copies Talk webhook shim
- Secret file convention: `~/.openclaw/.env.d/*.secret` (aligned across operator-init and `.env.example`)
- `subaru_core.py` — auth-check before capabilities; actionable error codes (`account_locked`, `device_not_authenticated`)
- `subaru-dispatch-exec.sh` — bash actuation gate (no grep on action names); friendly actuation-disabled JSON
- Docs: public README, Talk shim template, troubleshooting for lockout and Family Hub go-live

### Security

- `scrub-for-publish.sh` blocklist for operator PII, real room tokens, internal hosts
- Actuation off by default; live + actuation gates required before Tier 3 commands

## Initial development

- MySubaru / `subarulink` integration — [docs/SUBARU-VEHICLE.md](docs/SUBARU-VEHICLE.md)
- Skill `subaru-vehicle`, gates, cron `subaru-status-alert`, optional REST bridge
