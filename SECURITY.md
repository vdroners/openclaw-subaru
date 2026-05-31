# Security

## Secrets

- MySubaru credentials live in `~/.openclaw/.env` and `~/.openclaw/.env.d/*.secret` only.
- Never commit `.env`, `*.secret`, VIN, PIN, or passwords.
- Run `bash scripts/scrub-for-publish.sh` before every push.

## Actuation

- **MySubaru Connected Services** (`subarulink`) — remote lock/start/locate actuate the real vehicle.
- Keep `SUBARU_ACTUATION_ENABLED=0` until `subaru-gates.sh --check --live` and manual parked actuation tests pass.
- Actuation attempts are logged to `~/.openclaw/state/subaru-command-log.jsonl` (no secrets in log lines).

## Optional bridge

The Phase 2 REST bridge binds to loopback by default. Do not expose `:8790` on LAN without authentication.

## Reporting

Report security issues privately to the repo owner — do not open public issues for credential or actuation bypass findings.
