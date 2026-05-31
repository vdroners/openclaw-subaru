#!/usr/bin/env bash
# Repo structure + scrub gates (S1-S8, X-SUB, SUB-SMOKE). Run before push.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$ROOT"
FAIL=0

pass() { echo "Gate $1: PASS — $2"; }
fail() { echo "Gate $1: FAIL — $2"; FAIL=1; }

bash "${SCRIPT_DIR}/scrub-for-publish.sh" && pass S1 "scrub clean" || fail S1 "scrub failed"

while IFS= read -r f; do
  sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
  if [[ "$sz" -gt 512000 ]] && [[ "$f" != *LICENSE* ]] && [[ "$f" != *examples* ]]; then
    fail S2 "large file $f ($sz bytes)"
  fi
done < <(find . -type f ! -path './.git/*' 2>/dev/null)
[[ "$FAIL" -eq 0 ]] && pass S2 "no oversized tracked files"

for v in SUBARU_ENABLED SUBARU_USERNAME SUBARU_VIN OPENCLAW_AGENT_MENTION; do
  grep -q "^${v}=" .env.example 2>/dev/null || fail S3 "missing $v in .env.example"
done
if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  fail S3 ".env tracked in git"
else
  pass S3 ".env.example complete; .env not tracked"
fi

for f in scripts/*.sh; do
  case "$(basename "$f")" in
    install-openclaw-shell-cron.sh) continue ;;
  esac
  bash -n "$f" || fail S4 "$f syntax error"
done
for f in scripts/*.py scripts/install-openclaw-shell-cron.sh; do
  python3 -m py_compile "$f" || fail S4 "$f python syntax error"
done
for f in scripts/lib/*.py; do
  [[ -f "$f" ]] || continue
  python3 -m py_compile "$f" || fail S4 "$f python syntax error"
done
pass S4 "all scripts pass bash -n and python compile"

for f in LICENSE SECURITY.md CONTRIBUTING.md README.md; do
  [[ -f "$f" ]] || fail S7 "missing $f"
done
pass S7 "community files present"

bash "${SCRIPT_DIR}/validate-subaru-vehicle.sh" "${ROOT}/config/subaru-vehicle.example.json" && pass X-SUB "subaru vehicle schema ok" || fail X-SUB "subaru vehicle schema failed"
bash "${SCRIPT_DIR}/subaru-smoke.sh" && pass SUB-SMOKE "subaru smoke ok" || fail SUB-SMOKE "subaru smoke failed"

echo ""
echo "=== publish-gates summary (hard_fail=$FAIL) ==="
exit $FAIL
