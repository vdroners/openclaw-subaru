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
   bash scripts/subaru-gates.sh --check
   bash scripts/subaru-gates.sh --check --live   # after credentials work
   ```

8. After safe parked live tests (lock/start/stop), set `SUBARU_ACTUATION_ENABLED=1`.

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

| Symptom | Fix |
|---------|-----|
| `auth_invalid` | Re-run subarulink interactive login |
| `pin_invalid` | Check PIN file; run `subaru-vehicle.sh pin test` |
| `actuation_disabled` | Set `SUBARU_ACTUATION_ENABLED=1` after live gates |
| `rate_limited` on locate | Wait `SUBARU_LOCATE_MIN_INTERVAL_H` (default 2h) |
| Stale lock/door data | Run `fetch` then `condition`; some fields report UNKNOWN |

## Security

Unofficial API — may break without notice. Actuation commands are logged to `~/.openclaw/state/subaru-command-log.jsonl` (no secrets).
