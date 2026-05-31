# Gate matrix

Quality gates for the openclaw-subaru repo. Run `make gates` before release.

## Publish gates (`publish-gates.sh`)

| Gate | PASS criteria |
|------|---------------|
| S1 | `scrub-for-publish.sh` — no PII / blocklist hits |
| S2 | No tracked files > 512 KB (except LICENSE) |
| S3 | `.env.example` complete; `.env` not tracked |
| S4 | All `scripts/*.sh` pass `bash -n`; Python compiles |
| S7 | LICENSE, SECURITY, CONTRIBUTING, README present |
| X-SUB | `validate-subaru-vehicle.sh` on example JSON |
| SUB-SMOKE | `subaru-smoke.sh` dry-run CLI + schemas |

## Subaru gates (`subaru-gates.sh --check`)

Run `make gates` or `bash scripts/subaru-gates.sh --check`. When `SUBARU_ENABLED≠1`, emits `SUB-SKIP` WARN and exits 0.

| Gate | PASS criteria |
|------|---------------|
| SUB-SKIP | SUBARU_ENABLED not set — homelab without car creds |
| SUB-SEC | `validate-subaru-secrets.sh` — mode 600 secret files |
| SUB-X | `validate-subaru-vehicle.sh` — VIN + thresholds schema |
| SUB-VENV | venv import subarulink |
| SUB-CLI-DRY | read-only commands `--dry-run` → valid JSON |
| SUB-BLOCK-ACT | start blocked when `SUBARU_ACTUATION_ENABLED=0` |
| SUB-ALERT-DRY | `subaru-status-alert.sh --dry-run` |
| SUB-DISPATCH | `@openclaw subaru status` parses |
| SUB-SMOKE | `subaru-smoke.sh` (also in publish-gates) |
| SUB-NOSECRETS | gate stdout has no password/PIN patterns |

**Live read-only** (`--live`): SUB-LIVE-STATUS, SUB-LIVE-HEALTH, SUB-LIVE-MAPS — after auth bootstrap.

**Manual actuation** (safe parked context): SUB-LIVE-LOCK/UNLOCK/START/STOP/HORN/LIGHTS — then set `SUBARU_ACTUATION_ENABLED=1`.

## AI cron gates (`openclaw-ai-gates.sh --check`)

| Gate | PASS criteria |
|------|---------------|
| CAP-SUB | `subaru-status-alert` shell-direct job status=ok within 24h (when SUBARU_ENABLED=1) |
| AI-CRON-4 | Subaru manifest jobs disabled in OpenClaw agentTurn cron |

Operator guide: [SUBARU-VEHICLE.md](SUBARU-VEHICLE.md).
