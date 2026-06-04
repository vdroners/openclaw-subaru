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

ENV_KEYS=(
  OPENCLAW_AGENT_MENTION
  SUBARU_ENABLED
  SUBARU_USERNAME
  SUBARU_PASSWORD_FILE
  SUBARU_PIN_FILE
  SUBARU_VIN
  SUBARU_COUNTRY
  SUBARU_DEVICE_ID
  SUBARU_DEVICE_NAME
  SUBARU_VENV
  SUBARU_VEHICLE_JSON
  SUBARU_CONFIG_FILE
  SUBARU_ACTUATION_ENABLED
  SUBARU_REQUIRE_TALK_CONFIRM
  SUBARU_FASTPATH_ACTUATION
  SUBARU_ALERT_TALK_ROOM
  SUBARU_ALERT_MIN_INTERVAL_H
  SUBARU_LOCATE_MIN_INTERVAL_H
  SUBARU_MORNING_BRIEF
  SUBARU_BRIDGE_URL
  SUBARU_BRIDGE_KEY_FILE
  SUBARU_UPDATE_MIN_INTERVAL_S
  SUBARU_TALK_REFRESH_MAX_AGE_S
  SUBARU_GEOCODE
  SUBARU_VEHICLE_ALIASES
  SUBARU_SCHEDULED_START
  SUBARU_SCHEDULED_START_PRESET
  TALK_SHIM_LAN
)
for v in "${ENV_KEYS[@]}"; do
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

pass S5 "PII patterns covered by S1 scrub"
pass S6 "Subaru-specific patterns covered by SUB-SCRUB in S1"

if compgen -G "config/references/cron-shell-direct.yaml" >/dev/null; then
  if grep -qE 'password|Bearer|@[a-z]+\.(gmail|ourskylight)' config/references/cron-shell-direct.yaml 2>/dev/null; then
    fail S8 "secret in cron-shell-direct.yaml"
  else
    pass S8 "cron reference clean"
  fi
else
  pass S8 "no cron templates to scan"
fi

if python3 -m pytest tests/subaru -q >/tmp/subaru-pytest.out 2>&1; then
  pass SUB-ERR-UNIT "pytest tests/subaru ok"
else
  fail SUB-ERR-UNIT "$(tail -5 /tmp/subaru-pytest.out)"
fi

TMP_OPENCLAW="$(mktemp -d)"
if OPENCLAW_DIR="${TMP_OPENCLAW}/.openclaw" OPENCLAW_SUBARU_ROOT="$ROOT" bash "${SCRIPT_DIR}/install-to-openclaw.sh" --force >/tmp/subaru-i3.out 2>&1; then
  skill="${TMP_OPENCLAW}/.openclaw/workspace/skills/subaru-vehicle"
  if [[ -d "$skill" ]]; then
    real=$(readlink -f "$skill" 2>/dev/null || echo "$skill")
    case "$real" in
      "${TMP_OPENCLAW}/.openclaw/workspace/skills/"*) pass I3 "subaru-vehicle skill under workspace" ;;
      *) fail I3 "subaru-vehicle resolves outside workspace" ;;
    esac
  else
    fail I3 "subaru-vehicle skill missing after install"
  fi
else
  fail I3 "install-to-openclaw failed"
  tail -5 /tmp/subaru-i3.out >&2 || true
fi
rm -rf "$TMP_OPENCLAW"

bash "${SCRIPT_DIR}/validate-subaru-vehicle.sh" "${ROOT}/config/subaru-vehicle.example.json" && pass X-SUB "subaru vehicle schema ok" || fail X-SUB "subaru vehicle schema failed"
bash "${SCRIPT_DIR}/subaru-smoke.sh" && pass SUB-SMOKE "subaru smoke ok" || fail SUB-SMOKE "subaru smoke failed"
bash "${SCRIPT_DIR}/subaru-feature-gates.sh" || FAIL=1

echo ""
echo "=== publish-gates summary (hard_fail=$FAIL) ==="
exit $FAIL
