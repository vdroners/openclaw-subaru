# Subaru / MySubaru vehicle integration

OpenClaw skill + scripts for **MySubaru Connected Services** via the community [`subarulink`](https://github.com/G-Two/subarulink) library.

## Prerequisites

- Active MySubaru **Security Plus** subscription (US/Canada)
- MySubaru account email/password + 4-digit PIN
- Python venv at `~/.openclaw/venv-subaru`

## Operator setup

1. Copy secrets (mode **600**):

   ```bash
   mkdir -p ~/.openclaw/.env.d
   echo 'your-password' > ~/.openclaw/.env.d/subaru-password.secret
   echo '1234' > ~/.openclaw/.env.d/subaru-pin.secret
   chmod 600 ~/.openclaw/.env.d/subaru-*.secret
   ```

2. Configure `.env`:

   ```bash
   SUBARU_ENABLED=1
   SUBARU_USERNAME=you@example.com
   SUBARU_PASSWORD_FILE=~/.openclaw/.env.d/subaru-password.secret
   SUBARU_PIN_FILE=~/.openclaw/.env.d/subaru-pin.secret
   SUBARU_VIN=YOURVINHERE
   SUBARU_ACTUATION_ENABLED=0
   ```

3. Install Python deps:

   ```bash
   python3 -m venv ~/.openclaw/venv-subaru
   ~/.openclaw/venv-subaru/bin/pip install -r requirements.txt
   ```

4. Copy vehicle config:

   ```bash
   cp config/subaru-vehicle.example.json ~/.openclaw/config/subaru-vehicle.json
   # edit VIN, nickname, remote_start_preset
   ```

5. Auth bootstrap (first time):

   ```bash
   bash scripts/subaru-auth-bootstrap.sh
   # or interactive: ~/.openclaw/venv-subaru/bin/subarulink -i
   ```

6. Install to OpenClaw:

   ```bash
   bash scripts/install-to-openclaw.sh --force
   ```

7. Gates:

   ```bash
   make publish                              # Tier 0 (CI)
   make gates                                # Tier 0 + Tier 1 live reads
   bash scripts/subaru-gates.sh --check --live
   ```

8. Shell cron (CAP-SUB):

   ```bash
   make shell-cron
   ```

9. Tier 3 manual actuation (safe parked context):

   ```bash
   bash scripts/subaru-gates.sh --actuation
   bash scripts/subaru-record-live-pass.sh
   # then set SUBARU_ACTUATION_ENABLED=1
   ```

## Actuation safety tiers

| Tier | Commands | Requirements |
|------|----------|--------------|
| 0 | All read-only (`status`, `fetch`, `health-report`, …) | `SUBARU_ENABLED=1` |
| 1 | horn/lights `--stop` | PIN + actuation enabled |
| 2 | lock, stop, horn, lights, charge | Tier 1 + chat confirm for horn/lights |
| 3 | unlock, start | Tier 2 + pass file + explicit confirm |

Audit log: `~/.openclaw/state/subaru-command-log.jsonl` (no secrets).

## Phase 2 Docker bridge

Optional REST API on `127.0.0.1:8790`:

```bash
docker compose -f compose/docker-compose.subaru-bridge.yml up -d
make bridge-gates
```

| Method | Path | Command |
|--------|------|---------|
| GET | `/health` | health check |
| GET | `/status` | status |
| GET | `/summary` | summary |
| GET | `/capabilities` | capabilities |
| GET | `/condition` | condition |
| GET | `/health-report` | health-report |
| GET | `/locate` | locate |
| GET | `/presets` | presets list |
| POST | `/fetch` | fetch |
| POST | `/update` | update |
| POST | `/command` | arbitrary command body |

Set `SUBARU_BRIDGE_URL=http://127.0.0.1:8790` and optional `SUBARU_BRIDGE_KEY_FILE`.

## Command reference

See `skills/subaru-vehicle/SKILL.md`. All commands emit JSON on stdout.

## Cron alerts

`subaru-status-alert.sh` runs via `cron-shell-direct.yaml` (every 6h). Uses `fetch` + `health-report` — **never** `locate`.

Optional: `SUBARU_MORNING_BRIEF=1` + `subaru-morning-line.sh` for family digest hook (requires [openclaw-skylight](https://github.com/vdroners/openclaw-skylight) morning post integration).

Talk alerts use `SUBARU_ALERT_TALK_ROOM` or `SKYLIGHT_OPS_TALK_ROOM` when [openclaw-skylight](https://github.com/vdroners/openclaw-skylight) is installed (`talk-post.sh`).

## Phase 2 Docker bridge

Optional REST API on `127.0.0.1:8790` — see `services/subaru-bridge/` and `compose/docker-compose.subaru-bridge.yml`.

Set `SUBARU_BRIDGE_URL=http://127.0.0.1:8790` when running the bridge container.

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for the full matrix.

Unofficial API — may break without notice. Actuation commands are logged to `~/.openclaw/state/subaru-command-log.jsonl` (no secrets).
