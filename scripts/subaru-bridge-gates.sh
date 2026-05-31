#!/usr/bin/env bash
# Phase 2 bridge gates (optional). Requires running container on 127.0.0.1:8790
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh" 2>/dev/null || true

BASE="${SUBARU_BRIDGE_URL:-http://127.0.0.1:8790}"
KEY="${SUBARU_BRIDGE_API_KEY:-}"
if [[ -z "$KEY" && -n "${SUBARU_BRIDGE_KEY_FILE:-}" && -f "${SUBARU_BRIDGE_KEY_FILE/#\~/$HOME}" ]]; then
  KEY="$(cat "${SUBARU_BRIDGE_KEY_FILE/#\~/$HOME}")"
fi

FAIL=0
pass() { echo "Gate $1: PASS — $2"; }
fail() { echo "Gate $1: FAIL — $2" >&2; FAIL=1; }
warn() { echo "Gate $1: WARN — $2"; }

_auth_hdr=()
if [[ -n "$KEY" ]]; then
  _auth_hdr=(-H "X-API-Key: ${KEY}")
fi

code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "${BASE}/health" 2>/dev/null || echo 000)"
[[ "$code" == "200" ]] && pass SUB-BRIDGE-HEALTH "GET /health 200" || fail SUB-BRIDGE-HEALTH "HTTP $code"

if [[ -n "$KEY" ]]; then
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "${BASE}/status" 2>/dev/null || echo 000)"
  [[ "$code" == "401" ]] && pass SUB-BRIDGE-AUTH "missing key → 401" || fail SUB-BRIDGE-AUTH "expected 401 got $code"
else
  pass SUB-BRIDGE-AUTH "no API key configured (open bridge)"
fi

_compare_route() {
  local route="$1"
  local cli_cmd="$2"
  local http_path="$3"
  local method="${4:-GET}"
  bash "${SCRIPT_DIR}/subaru-vehicle.sh" $cli_cmd >/tmp/subaru-bridge-cli.json 2>/dev/null || return 1
  if [[ "$method" == "POST" ]]; then
    curl -sS --max-time 15 "${_auth_hdr[@]}" -X POST "${BASE}${http_path}" >/tmp/subaru-bridge-http.json 2>/dev/null || return 1
  else
    curl -sS --max-time 15 "${_auth_hdr[@]}" "${BASE}${http_path}" >/tmp/subaru-bridge-http.json 2>/dev/null || return 1
  fi
  python3 - /tmp/subaru-bridge-cli.json /tmp/subaru-bridge-http.json <<'PY'
import json, sys
cli = json.load(open(sys.argv[1]))
http = json.load(open(sys.argv[2]))
for key in ("ok", "command"):
    if cli.get(key) != http.get(key):
        print(f"mismatch {key}: cli={cli.get(key)} http={http.get(key)}", file=sys.stderr)
        sys.exit(1)
sys.exit(0)
PY
}

if [[ "$code" == "200" ]]; then
  for spec in "status:status:/status:GET" "capabilities:capabilities:/capabilities:GET" "health-report:health-report:/health-report:GET" "condition:condition:/condition:GET"; do
    IFS=: read -r label cli path method <<<"$spec"
    if _compare_route "$label" "$cli" "$path" "$method"; then
      pass SUB-BRIDGE-PARITY "$label CLI vs HTTP"
    else
      fail SUB-BRIDGE-PARITY "$label mismatch or unreachable"
    fi
  done
else
  warn SUB-BRIDGE-PARITY "skipped — bridge not healthy"
fi

echo "=== subaru-bridge-gates (hard_fail=${FAIL}) ==="
exit "$FAIL"
