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
| **Scripts** | `subaru-vehicle.sh` facade, gates, auth bootstrap, Talk alerts, optional morning brief hook |
| **Config** | JSON Schema for `subaru-vehicle.json`, cron stub, gate fixtures |
| **Docs** | Operator guide, full SUB-* gate matrix, webhook relay snippet |

This repo is **private** and separate from [openclaw-skylight](https://github.com/vdroners/openclaw-skylight) (Skylight calendar / household automation). Both install into the same `~/.openclaw` tree.

---

## Quick start

```bash
git clone git@github.com:vdroners/openclaw-subaru.git
cd openclaw-subaru

cp .env.example ~/.openclaw/.env   # merge with existing OpenClaw env
# Set SUBARU_* vars — see docs/SUBARU-VEHICLE.md

python3 -m venv ~/.openclaw/venv-subaru
~/.openclaw/venv-subaru/bin/pip install -r requirements.txt

cp config/subaru-vehicle.example.json ~/.openclaw/config/subaru-vehicle.json
bash scripts/subaru-auth-bootstrap.sh
bash scripts/install-to-openclaw.sh --force

make smoke
make gates
```

---

## Gate matrix

```bash
make smoke          # SUB-SMOKE — dry-run CLI + schema fixtures
make gates          # publish-gates + subaru-gates + ai-gates (CAP-SUB)
bash scripts/subaru-gates.sh --check --live      # after credentials work
bash scripts/subaru-gates.sh --check --actuation # manual parked tests only
```

Full gate reference: [docs/GATES.md](docs/GATES.md). Operator setup: [docs/SUBARU-VEHICLE.md](docs/SUBARU-VEHICLE.md).

---

## Repository layout

```
openclaw-subaru/
├── skills/subaru-vehicle/     # OpenClaw skill (copied on install)
├── scripts/                   # Bash + Python CLI (symlinked to ~/.openclaw/scripts)
├── config/                    # Schemas + example vehicle JSON
├── docs/                      # Operator + gate docs
├── tests/subaru/              # Health scorecard unit tests
├── compose/                   # Optional Phase 2 Docker bridge
└── services/subaru-bridge/    # Loopback REST bridge (:8790)
```

---

## Optional integrations

| Integration | How |
|-------------|-----|
| **Nextcloud Talk alerts** | Set `SUBARU_ALERT_TALK_ROOM` or install openclaw-skylight for `talk-post.sh` |
| **Morning brief line** | `SUBARU_MORNING_BRIEF=1` + skylight family morning post |
| **Webhook fast-path** | [docs/templates/nc-webhook-relay-subaru-snippet.md](docs/templates/nc-webhook-relay-subaru-snippet.md) |
| **REST bridge** | `docker compose -f compose/docker-compose.subaru-bridge.yml up -d` |

---

## Related projects

- **[openclaw-skylight](https://github.com/vdroners/openclaw-skylight)** — Skylight frame + household propose-first automation
- **[NC-GCS](https://github.com/vdroners/NC-GCS)** — fleet ground control (separate repo)

---

## License

MIT — see [LICENSE](LICENSE).
