# Troubleshooting — openclaw-subaru

## Auth / session

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `auth_invalid` / SUB-AUTH fail | Expired session or wrong password | Update `~/.openclaw/.env.d/subaru-password` after a MySubaru password change; verify with `subaru-vehicle.sh auth check` |
| `account_locked` / `accountLocked` | Too many failed logins or 2FA attempts | Wait 30–60 minutes; **do not** loop `request_auth_code` or IMAP auto-submit |
| SUB-2FA WARN / `device_not_authenticated` | Device not registered on this host | **One** registration: `bash ~/.openclaw/scripts/subaru-device-register.sh --request` (same session for request + submit) |
| `auth_incomplete` | Missing username/password/PIN files | Check `SUBARU_*_FILE` paths and mode 600 |

## PIN

| Symptom | Fix |
|---------|-----|
| `pin_invalid` | Verify PIN file; run `subaru-vehicle.sh pin test` |
| `pin_lockout` | Wait for MySubaru lockout to clear; do not retry rapidly |
| SUB-PIN-LIVE WARN | Session ok but PIN wrong or missing file |

## Data freshness

| Symptom | Fix |
|---------|-----|
| Stale locks/doors UNKNOWN | Run `fetch` then `condition` |
| SUB-STALE WARN/FAIL | Run `update` manually once; check vehicle connectivity |
| Empty summary | Run `fetch` before `health-report` |

## Locate / rate limit

| Symptom | Fix |
|---------|-----|
| `rate_limited` on locate | Wait `SUBARU_LOCATE_MIN_INTERVAL_H` (default 2h) or use `--force` with operator approval |
| SUB-LOCATE fail | Rate limit or weak GPS; retry later |

## Actuation

| Symptom | Fix |
|---------|-----|
| `actuation_disabled` | Expected until Tier 3 manual gates pass; run `subaru-record-live-pass.sh` then set `SUBARU_ACTUATION_ENABLED=1` |
| SUB-ACT-PASS-FILE fail | Missing `~/.openclaw/state/subaru-gates-live-pass.json` |
| Start fails `preset_missing` | Set `remote_start_preset` in vehicle JSON or pass `--preset` |

## Talk / cron

| Symptom | Fix |
|---------|-----|
| No alert posts | Set `SUBARU_ALERT_TALK_ROOM` or install openclaw-skylight for `talk-post.sh` |
| CAP-SUB fail | Install shell cron: `make shell-cron`; verify `subaru-status-alert` timer |
| SUB-CRON-DEDUP WARN | Normal if alert posted recently within min interval |
| `Connection refused` in `journalctl -u talk-webhook-shim` | OpenClaw plugin webhook on **:8787** is down; Subaru fast-path on **:8788** still works. Start OpenClaw gateway/plugin or ignore if only using `@openclaw subaru …` |
| `FLIGHT EVENT: openclaw gateway down` spam / shim tracebacks | Upgrade shim (drops system broadcasts); ensure the bot's actor id (e.g. `users/<bot>`) is in `OPENCLAW_ACTOR_IDS` |
| Calendar/chore `@openclaw` messages get no reply | Same as :8787 down — non-Subaru Talk needs the OpenClaw upstream, not just the shim |
| `fetch` shows `ok: false` in command log | Often benign if `status`/`condition` succeed; run `update` once; API may return false when cache is already fresh |
| Family Hub status shows wrong odometer / range / ignition | Stale MySubaru cache. Talk `status` now auto-runs `update` when the cache is older than `SUBARU_TALK_REFRESH_MAX_AGE_S` (default 300s) and renders the richer `summary` deck. If MySubaru rate-limits the refresh, the reply leads with `(cached ~Nm old - could not refresh)` so old numbers are never shown as live |
| Reply says `IGNITION_OFF` while driving | `VEHICLE_STATE_TYPE` reflects the last successful poll. Compare against the MySubaru app: if the app also shows OFF, telemetry was simply stale (now auto-refreshed); ignition state is a poll snapshot, not a live stream |
| Talk refresh fires too often / hits update rate limits | Raise `SUBARU_TALK_REFRESH_MAX_AGE_S` (e.g. `900`); also set `SUBARU_UPDATE_MIN_INTERVAL_S` (e.g. `600`) so repeated auto-refreshes coalesce and a rate-limited update isn't retried on every poll |
| Shim reachable from other LAN hosts unexpectedly | The shim now binds `127.0.0.1` by default. To expose it (NC bot on another host) set `TALK_SHIM_LAN=1` or `TALK_SHIM_HOST=0.0.0.0` |
| Condition alert never fires for a door/unlock | `subaru-status-alert.sh` posts on the *transition*; confirm the cron runs and `SUBARU_ALERT_TALK_ROOM` is set. The condition signature is stored in `state/subaru-last-alert.json` (`conditions`) and only re-alerts when it reappears |
| Scheduled start did nothing | Needs `SUBARU_SCHEDULED_START=1` AND `SUBARU_ACTUATION_ENABLED=1`; run `subaru-scheduled-start.sh --dry-run` to see the gate decision |
| `subaru <nickname>` not recognized in Talk | Add the nickname→VIN map to `SUBARU_VEHICLE_ALIASES` (JSON) in `~/.openclaw/.env` |
| Location shows coordinates, not a place name | Reverse geocoding is opt-in: set `SUBARU_GEOCODE=1` (uses OSM Nominatim, cached in `state/subaru-geocode-cache.json`) |

## Bridge (Phase 2)

| Symptom | Fix |
|---------|-----|
| SUB-BRIDGE-HEALTH fail | Start bridge: `docker compose -f compose/docker-compose.subaru-bridge.yml up -d` |
| SUB-BRIDGE-AUTH fail | Set `SUBARU_BRIDGE_API_KEY` or key file; expect 401 without header |
| SUB-BRIDGE-PARITY fail | Bridge and CLI must both use live credentials (`SUBARU_ENABLED=1`) |

## Gates quick reference

```bash
make publish                    # Tier 0 — CI safe
make gates                      # Tier 0 + AI + Tier 1 (needs SUBARU_ENABLED=1 for live reads)
bash scripts/subaru-gates.sh --check --live   # Tier 2
bash scripts/subaru-gates.sh --actuation      # Tier 3 runbook (manual)
make bridge-gates               # Phase 2 optional
```
