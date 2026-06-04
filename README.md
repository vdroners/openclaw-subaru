# openclaw-subaru

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-2026.4+-green.svg)](https://github.com/openclaw/openclaw)

**OpenClaw skill + shell automation for MySubaru Connected Services** — vehicle status, health scorecard, locate, and gated remote actuation via [`subarulink`](https://github.com/G-Two/subarulink).

> **Unofficial MySubaru API.** Subaru may change without notice. **Actuation is off by default** (`SUBARU_ACTUATION_ENABLED=0`) until live gates pass in a safe parked context.

---

## What this project is

| Bundle | Purpose |
|--------|---------|
| **Skill** | `subaru-vehicle` — agent instructions for status, health, locate, lock/unlock, remote start |
| **Scripts** | `subaru-vehicle.sh` facade, gates, auth bootstrap, Talk fast-path, optional morning brief hook |
| **Config** | JSON Schema for `subaru-vehicle.json`, cron stub, gate fixtures |
| **Docs** | Operator guide, SUB-* gate matrix, Talk webhook shim templates |

Installs into the same `~/.openclaw` tree as [openclaw-skylight](https://github.com/vdroners/openclaw-skylight) (household automation) but is **standalone** — Skylight is optional.

---

## Quick start

```bash
git clone https://github.com/vdroners/openclaw-subaru.git
cd openclaw-subaru

# Merge env keys into ~/.openclaw/.env — see .env.example
bash scripts/subaru-operator-init.sh   # optional interactive bootstrap

python3 -m venv ~/.openclaw/venv-subaru
~/.openclaw/venv-subaru/bin/pip install -r requirements.txt

cp config/subaru-vehicle.example.json ~/.openclaw/config/subaru-vehicle.json
# Edit VIN, nickname, device_id

bash scripts/subaru-auth-bootstrap.sh
bash scripts/subaru-device-register.sh --request   # one-time 2FA
bash scripts/install-to-openclaw.sh --force

make smoke
make publish    # full pre-push gate (scrub + pytest + smoke)
```

Operator guide: [docs/SUBARU-VEHICLE.md](docs/SUBARU-VEHICLE.md)

---

## Talk fast-path (no LLM)

For Nextcloud Talk, `@openclaw subaru status` should bypass the LLM entirely:

| Port | Role |
|------|------|
| **8788** | Talk webhook **shim** — Subaru fast-path + forward other events |
| **8787** | OpenClaw plugin webhook (set `webhookPort` in `openclaw.json`) |
| **8789** | Optional relay secondary path |
| **8790** | Optional REST bridge (loopback) |

Setup: [docs/templates/TALK-WEBHOOK-SHIM.md](docs/templates/TALK-WEBHOOK-SHIM.md)

Supported Talk phrases include `@openclaw subaru status`, `@openclaw subaru locate`, and `{mention-user1} subaru status` (NC mention chip).

Talk status reads auto-refresh stale telemetry (`SUBARU_TALK_REFRESH_MAX_AGE_S`,
default 300s) and coalesce repeated refreshes (`SUBARU_UPDATE_MIN_INTERVAL_S`) so
MySubaru rate limits are respected. The shim binds loopback by default — set
`TALK_SHIM_LAN=1` only if the NC bot lives on another host.

---

## Proactive automation

| Feature | How |
|---------|-----|
| **Condition alerts** | `subaru-status-alert.sh` (cron) posts once when a door opens, the car is left unlocked, a window is down, fuel/range/tire crosses a threshold, or ignition is left on — deduped per condition |
| **Scheduled remote start** | `subaru-scheduled-start.sh` (cron) — needs `SUBARU_SCHEDULED_START=1` + `SUBARU_ACTUATION_ENABLED=1`; optional `SUBARU_SCHEDULED_START_DAYS`/`_PRESET`/`_ROOM` |
| **Weekly trip digest** | Morning brief records a daily odometer sample and appends `Driven last 7d: N mi` |
| **Multi-vehicle** | `subaru <nickname> status` via `SUBARU_VEHICLE_ALIASES`, or `subaru-vehicle.sh --vin <VIN> ...` |
| **Reverse geocode** | `SUBARU_GEOCODE=1` turns locate coordinates into a place name (cached, OSM Nominatim) |

---

## Gate matrix

```bash
make smoke          # SUB-SMOKE — dry-run CLI + schema fixtures
make publish        # scrub + publish-gates + pytest + smoke
make gates          # publish + subaru-gates + ai-gates (CAP-SUB)
bash scripts/subaru-gates.sh --check --live      # after credentials work
bash scripts/subaru-gates.sh --check --actuation # manual parked tests only
```

Full reference: [docs/GATES.md](docs/GATES.md) · Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## Repository layout

```
openclaw-subaru/
├── skills/subaru-vehicle/     # OpenClaw skill (copied on install)
├── scripts/                   # Bash + Python CLI + lib/ (symlinked to ~/.openclaw/scripts)
├── config/                    # Schemas + example vehicle JSON
├── docs/                      # Operator + gate docs + Talk shim templates
├── tests/subaru/              # 100+ pytest cases (core, dispatch, talk, health, bridge, conditions, trips, geocode)
├── compose/                   # Optional Docker bridge
└── services/subaru-bridge/    # Loopback REST bridge (:8790)
```

---

## Optional integrations

| Integration | How |
|-------------|-----|
| **Nextcloud Talk alerts** | Set `SUBARU_ALERT_TALK_ROOM` or install openclaw-skylight for `talk-post.sh` |
| **Morning brief line** | `SUBARU_MORNING_BRIEF=1` + skylight family morning post |
| **Talk webhook shim** | [docs/templates/TALK-WEBHOOK-SHIM.md](docs/templates/TALK-WEBHOOK-SHIM.md) |
| **Webhook relay snippet** | [docs/templates/nc-webhook-relay-subaru-snippet.md](docs/templates/nc-webhook-relay-subaru-snippet.md) |
| **REST bridge** | `docker compose -f compose/docker-compose.subaru-bridge.yml up -d` |
| **Shell cron jobs** | `make shell-cron` (see `config/references/cron-shell-direct.yaml`) |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run `make publish` before opening a PR.

---

## Related projects

- **[openclaw-skylight](https://github.com/vdroners/openclaw-skylight)** — Skylight calendar / household propose-first automation
- **[NC-GCS](https://github.com/vdroners/NC-GCS)** — fleet ground control (separate repo)

---

## License

MIT — see [LICENSE](LICENSE). Changelog: [CHANGELOG.md](CHANGELOG.md).
