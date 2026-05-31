# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Go-live: `subaru-device-register.sh` + `--request` one-shot 2FA flow; `subaru-format-talk-reply.sh` for Family Hub plain-text replies
- Error codes: `account_locked`, `device_not_authenticated`; `subarulink_error_code_from_message()` helper
- Tests: formatter smoke, auth-check dry envelope, expanded exception mapping
- Relay template: dispatch-exec + formatter + talk-post fast-path (operator-local `nc-webhook-relay.py`)

### Changed

- `subaru_core.py` — auth-check/connect/vehicles-list/pin-test before capabilities fetch; stable connect error mapping; charge blocked when actuation disabled
- `subaru_cli.py` — fix missing `import os` for live CLI
- `subaru-gates.sh` — `MENTION` default, JSON parser tolerates trailing `SUBARU_ERR`; charge removed from read-only dry matrix
- Docs: Family Hub go-live checklist in SUBARU-VEHICLE.md; account lockout recovery in TROUBLESHOOTING.md
- `subaru-vehicle.example.json` — stable example `device_id`

### Added

- Go-live: `subaru-device-register.sh` + `--request` one-shot 2FA flow; `subaru-format-talk-reply.sh` for Family Hub plain-text replies
- Error codes: `account_locked`, `device_not_authenticated`; `subarulink_error_code_from_message()` helper
- Relay template: Subaru fast-path via `subaru-dispatch-exec.sh` + formatter + `talk-post.sh`
- Tests: formatter smoke, auth-check dry envelope, expanded exception mapping

### Changed

- `subaru_core.py` — auth-check/connect/vehicles-list/pin-test before capabilities fetch; stable connect error mapping; charge gated like other actuation in dry-run
- `subaru_cli.py` — fix missing `import os` for live CLI
- `subaru-gates.sh` — `MENTION` default; JSON parser tolerates trailing `SUBARU_ERR`; charge removed from read-only dry matrix
- `subaru-operator-init.sh` — auto-assign stable `device_id` when missing/suspicious
- Docs: Family Hub go-live checklist, lockout recovery in TROUBLESHOOTING.md

### Added

- Phase 2: alert dedup enforcement, pass-file boolean validation, bridge HTTP client (`--bridge` / `SUBARU_BRIDGE_URL`)
- `subaru-dispatch-exec.sh`, `subaru-operator-init.sh`, `subaru_bridge_client.py`, `subaru_alert.py`, `subaru_pass_file.py`
- Gates: SUB-BLOCK-ACT-ALL, SUB-TPMS, SUB-RES, SUB-LEVEL1, SUB-DISPATCH-EXEC-DRY, SUB-MORNING-DRY, SUB-CMD-LOG, SUB-AUTH-CONNECT, publish S5/S6/S8
- Bridge: Docker entrypoint secret loading, expanded SUB-BRIDGE-PARITY (6 routes + score/verdict)
- pytest suite expanded to 32+ cases

### Changed

- `subaru-dispatch.sh` — `health` / `health-report` → scorecard action; fix sed parsing on GNU sed
- `subaru-status-alert.sh` — respects `SUBARU_ALERT_MIN_INTERVAL_H` with escalation bypass
- `subaru-gates.sh` — full dry-run command matrix, Tier 1/2 gate expansion, pass-file content validation
- `subaru-bridge-gates.sh` — prefetch parity, summary/fetch routes

### Added (parity pass)
- `subaru-dispatch-test.sh`, `subaru-record-live-pass.sh`, `load-agent-env.sh`
- Bridge `/condition` route + SUB-BRIDGE-PARITY; SUB-CRON-DEDUP in ai-gates
- Docs: `docs/plans/subaru-integration-v3.md`, `docs/TROUBLESHOOTING.md`, expanded GATES.md

### Changed

- `subaru-gates.sh` — Tier 1/2 live read gates, SUB-ACT-PASS-FILE, expanded SUB-DISPATCH
- `subaru-smoke.sh` — all R* dry-run commands + schema validation
- `publish-gates.sh` — SUB-ERR-UNIT, I3 install gate, full S3 env keys, SUB-SCRUB

## Initial release

- MySubaru / `subarulink` integration — [docs/SUBARU-VEHICLE.md](docs/SUBARU-VEHICLE.md)
- Skill `subaru-vehicle`, gates, cron `subaru-status-alert`, optional REST bridge
