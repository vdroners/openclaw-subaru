# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Initial **openclaw-subaru** repo — extracted from openclaw-skylight
- MySubaru / `subarulink` integration: status, health-report, locate, lock/unlock, remote start/stop, horn/lights, climate presets — [docs/SUBARU-VEHICLE.md](docs/SUBARU-VEHICLE.md)
- Skill `subaru-vehicle`, gates `subaru-gates.sh` / `subaru-smoke.sh`, cron `subaru-status-alert`
- Optional Phase 2 REST bridge: `services/subaru-bridge/` on loopback `:8790`
- Gates: SUB-* matrix in [docs/GATES.md](docs/GATES.md); Makefile targets `gates`, `smoke`
