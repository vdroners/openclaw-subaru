# Contributing

Thanks for helping improve OpenClaw + MySubaru integrations.

## Before you push

```bash
make publish      # structure, syntax, schema, scrub, SUB-SMOKE
bash scripts/scrub-for-publish.sh
```

On homelab with `SUBARU_ENABLED=1`, also verify:

```bash
bash scripts/subaru-gates.sh --check --live
```

Must report **`hard_fail=0`** before tagging a release.

## Scope

**In scope:** MySubaru / subarulink wrapper, health scorecard, gated actuation, Talk alert cron, optional REST bridge.

**Out of scope:** Skylight calendar automation (see openclaw-skylight), NC-GCS fleet ops, operator-private runbooks.

## Pull requests

1. One logical change per PR
2. Update `CHANGELOG.md` under `[Unreleased]`
3. No real VIN, PIN, passwords, Talk room tokens, or home paths in committed files
4. Document new gates in `docs/GATES.md`
5. Extend `README.md` if you add a new script bundle or config file

## OpenClaw project conventions

| Rule | Why |
|------|-----|
| `set -euo pipefail` on bash entrypoints | Fail fast; safe for cron |
| Secrets in `~/.openclaw/.env.d/*.secret` (mode 600) | Never in git or logs |
| `--dry-run` on gate paths that must not mutate | CI + homelab QA |
| JSON on stdout from `subaru-vehicle.sh` | Agent + dispatch parsing |
| `SUBARU_ACTUATION_ENABLED=0` until live gates pass | Real vehicle safety |
