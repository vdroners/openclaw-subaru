# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
