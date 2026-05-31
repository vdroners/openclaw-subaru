# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Parity pass: expanded gate matrix (Tier 0–3), pytest suite, CI scrub-check, dispatch phrase tests
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
