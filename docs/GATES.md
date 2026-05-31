# Gate matrix

Quality gates for the openclaw-subaru repo. Full v3 traceability: [plans/subaru-integration-v3.md](plans/subaru-integration-v3.md).

## Tier 0 — Publish / CI (`make publish`)

No credentials required.

| Gate | PASS criteria | Automated |
|------|---------------|-----------|
| S1 | `scrub-for-publish.sh` — no PII / blocklist hits | yes |
| SUB-SCRUB | No MySubaru emails / stray VIN in tracked tree | yes |
| S2 | No tracked files > 512 KB | yes |
| S3 | All `SUBARU_*` keys in `.env.example`; `.env` not tracked | yes |
| S4 | bash -n + Python compile | yes |
| S7 | LICENSE, SECURITY, CONTRIBUTING, README | yes |
| SUB-ERR-UNIT | `pytest tests/subaru` | yes |
| I3 | Temp install → `subaru-vehicle` skill under workspace | yes |
| X-SUB | Example vehicle JSON validates | yes |
| SUB-SMOKE | All R* commands dry-run + schema envelope | yes |

## Tier 1 — `subaru-gates.sh --check`

When `SUBARU_ENABLED≠1` → `SUB-SKIP` WARN, exit 0.

When enabled, runs dry-run gates plus live read-only network checks:

| Gate | PASS criteria |
|------|---------------|
| SUB-SEC | Secret files mode 600 |
| SUB-X | Operator vehicle JSON valid |
| SUB-VENV | venv imports subarulink |
| SUB-CLI-DRY | Every R* command `--dry-run` |
| SUB-BLOCK-ACT | `start` → `actuation_disabled` |
| SUB-MAP-DRY | `maps-link` URL format |
| SUB-ALERT-DRY | status-alert dry-run |
| SUB-DISPATCH | Fast-path phrase matrix (`subaru-dispatch-test.sh`) |
| SUB-SMOKE | smoke script |
| SUB-NOSECRETS | Gate stdout clean |
| SUB-ACT-PASS-FILE | Pass file required when actuation enabled |
| SUB-2FA / SUB-AUTH | `auth check` + device_registered |
| SUB-SUMMARY | Live summary text |
| SUB-CAP | remote + RES capabilities |
| SUB-FETCH | Live fetch |
| SUB-CONDITION | Condition block |
| SUB-MIL | Health block |
| SUB-PRESETS / SUB-PRESET-DEFAULT | Preset list + default in config |
| SUB-HEALTH | health-report score + verdict |
| SUB-STATUS | Live status |
| SUB-EV-SKIP | WARN when not EV |
| SUB-PIN-LIVE | WARN on pin failure |

## Tier 2 — `subaru-gates.sh --check --live`

| Gate | PASS criteria |
|------|---------------|
| SUB-LOCATE | lat/lon numeric |
| SUB-VEHICLES | Configured VIN in list |
| SUB-STALE | Data age WARN >24h, FAIL >72h |
| SUB-UPDATE | Manual update ok (cron never calls update) |

## Tier 3 — Manual actuation

Not automated in CI. Operator runbook:

```bash
bash scripts/subaru-gates.sh --actuation   # prints checklist
bash scripts/subaru-record-live-pass.sh    # writes pass file
# set SUBARU_ACTUATION_ENABLED=1
```

Gates: SUB-LIVE-LOCK, SUB-LIVE-UNLOCK, SUB-LIVE-UNLOCK-DRIVER, SUB-LIVE-START, SUB-LIVE-STOP, SUB-LIVE-HORN, SUB-LIVE-LIGHTS, SUB-LIVE-CHARGE (EV only).

## AI cron (`make ai-gates`)

| Gate | PASS criteria |
|------|---------------|
| CAP-SUB | Alert cron ok within 24h when enabled |
| AI-CRON-4 | Shell-direct job disabled in agentTurn cron |
| SUB-CRON-DEDUP | Alert min-interval respected |

## Phase 2 bridge (`make bridge-gates`)

| Gate | PASS criteria |
|------|---------------|
| SUB-BRIDGE-HEALTH | GET /health 200 |
| SUB-BRIDGE-AUTH | Missing API key → 401 |
| SUB-BRIDGE-PARITY | CLI vs HTTP match for status, capabilities, health-report, condition |

Operator guide: [SUBARU-VEHICLE.md](SUBARU-VEHICLE.md). Troubleshooting: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
