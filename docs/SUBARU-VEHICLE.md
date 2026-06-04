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

   Or use the Phase 2 bootstrap helper (creates local files only — never commits secrets):

   ```bash
   bash scripts/subaru-operator-init.sh
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

Set `SUBARU_BRIDGE_URL=http://127.0.0.1:8790` and optional `SUBARU_BRIDGE_KEY_FILE`. When the bridge URL is set, `subaru-vehicle.sh` passes `--bridge` to the CLI automatically.

## Go-live checklist (Family Hub)

1. Unlock MySubaru at [mysubaru.com](https://www.mysubaru.com) if the account is locked.
2. Write secrets locally (mode **600**, never commit):
   - `~/.openclaw/.env.d/subaru-password` — one line, permanent password
   - `~/.openclaw/.env.d/subaru-pin` — one line, 4-digit MySubaru PIN
3. Ensure `~/.openclaw/config/subaru-vehicle.json` has a **stable** `device_id` (not a Talk room token).
4. Install scripts: `bash scripts/install-to-openclaw.sh --force` from your openclaw-subaru clone
5. **One** 2FA registration (same session — do not loop):
   ```bash
   bash ~/.openclaw/scripts/subaru-device-register.sh --request
   ```
6. Verify: `bash ~/.openclaw/scripts/subaru-vehicle.sh auth check` → `device_registered: true`
7. Patch `~/.openclaw/nc-webhook-relay.py` with the Subaru fast-path (see [templates/nc-webhook-relay-subaru-snippet.md](templates/nc-webhook-relay-subaru-snippet.md)); restart the relay.
8. Family Hub test phrase: `@openclaw subaru status` (set `OPENCLAW_AGENT_MENTION` if your agent alias differs).

## Talk fast-path

Parse-only: `subaru-dispatch.sh "@openclaw subaru status"`.

Execute (runs `subaru-vehicle.sh`): `subaru-dispatch-exec.sh --dry-run "…"` or without `--dry-run` from Talk hooks.

## Command reference

See `skills/subaru-vehicle/SKILL.md`. All commands emit JSON on stdout.

## Cron alerts

`subaru-status-alert.sh` runs via `cron-shell-direct.yaml` (every 6h). Uses `fetch` + `health-report` — **never** `locate`.

Optional: `SUBARU_MORNING_BRIEF=1` + `subaru-morning-line.sh` for family digest hook (requires [openclaw-skylight](https://github.com/vdroners/openclaw-skylight) morning post integration).

Talk alerts use `SUBARU_ALERT_TALK_ROOM` or `SKYLIGHT_OPS_TALK_ROOM` when [openclaw-skylight](https://github.com/vdroners/openclaw-skylight) is installed (`talk-post.sh`).

Alert dedup: `SUBARU_ALERT_MIN_INTERVAL_H` (default 6). Inspect with `subaru-status-alert.sh --would-post`.

### Proactive condition alerts

`subaru-status-alert.sh` also posts once when an actionable condition first
appears — a door open, the car left unlocked, a window/sunroof down, fuel/range
or tire pressure crossing a threshold, ignition left on, or a MIL. The active
condition set is stored in `state/subaru-last-alert.json` (`conditions`) so a
condition only re-alerts when it reappears (no per-poll spam).

### Scheduled remote start

`subaru-scheduled-start.sh` is a cron wrapper around `start --preset`. Cron drives
the time; the wrapper enforces the gates and optionally filters by weekday:

```bash
# 06:50 on weekdays (in your crontab / systemd timer)
SUBARU_SCHEDULED_START=1 SUBARU_ACTUATION_ENABLED=1 \
SUBARU_SCHEDULED_START_PRESET="Winter" \
SUBARU_SCHEDULED_START_DAYS="Mon Tue Wed Thu Fri" \
bash ~/.openclaw/scripts/subaru-scheduled-start.sh
```

Run with `--dry-run` to see the gate decision without actuating.

### Multi-vehicle

Target a specific VIN per command with `subaru-vehicle.sh --vin <VIN> status`. In
Talk, map spoken nicknames to VINs via `SUBARU_VEHICLE_ALIASES` (JSON) so
`@openclaw subaru outback status` resolves automatically.

### Trip digest + reverse geocode

The morning brief records one odometer/fuel sample per day (`state/subaru-trips.jsonl`)
and appends a rolling `Driven last 7d: N mi` digest. Set `SUBARU_GEOCODE=1` to turn
locate coordinates into a cached place name in Talk replies (OSM Nominatim).

### Talk read freshness + rate limits

Talk status reads auto-refresh when telemetry is older than
`SUBARU_TALK_REFRESH_MAX_AGE_S` (default 300s). `SUBARU_UPDATE_MIN_INTERVAL_S`
coalesces repeated update/fetch attempts so a rate-limited refresh is not retried
on every message; when serving cached data the reply leads with a stale notice.

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for the full matrix.

Unofficial API — may break without notice. Actuation commands are logged to `~/.openclaw/state/subaru-command-log.jsonl` (no secrets).
