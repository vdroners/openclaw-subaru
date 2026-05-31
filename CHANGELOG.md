# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
