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
  auth_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "${BASE}/status" 2>/dev/null || echo 000)"
  [[ "$auth_code" == "401" ]] && pass SUB-BRIDGE-AUTH "missing key → 401" || fail SUB-BRIDGE-AUTH "expected 401 got $auth_code"
else
  warn SUB-BRIDGE-AUTH "no API key configured (open bridge on loopback only)"
fi

_compare_route() {
  local label="$1"
  local method="$2"
  local path="$3"
  shift 3
  bash "${SCRIPT_DIR}/subaru-vehicle.sh" "$@" >/tmp/subaru-bridge-cli.json 2>/dev/null || return 1
  if [[ "$method" == "POST" ]]; then
    curl -sS --max-time 15 "${_auth_hdr[@]}" -X POST "${BASE}${path}" >/tmp/subaru-bridge-http.json 2>/dev/null || return 1
  else
    curl -sS --max-time 15 "${_auth_hdr[@]}" "${BASE}${path}" >/tmp/subaru-bridge-http.json 2>/dev/null || return 1
  fi
  python3 - /tmp/subaru-bridge-cli.json /tmp/subaru-bridge-http.json "$label" <<'PY'
import json, sys
cli = json.load(open(sys.argv[1]))
http = json.load(open(sys.argv[2]))
label = sys.argv[3]
for key in ("ok", "command"):
    if cli.get(key) != http.get(key):
        sys.exit(1)
if label == "health-report":
    for key in ("score", "verdict"):
        if cli.get("data", {}).get(key) != http.get("data", {}).get(key):
            sys.exit(1)
sys.exit(0)
PY
}

if [[ "$code" == "200" ]]; then
  _compare_route status GET /status status && pass SUB-BRIDGE-PARITY "status" || fail SUB-BRIDGE-PARITY "status"
  _compare_route summary GET /summary summary && pass SUB-BRIDGE-PARITY "summary" || fail SUB-BRIDGE-PARITY "summary"
  _compare_route capabilities GET /capabilities capabilities && pass SUB-BRIDGE-PARITY "capabilities" || fail SUB-BRIDGE-PARITY "capabilities"
  _compare_route health-report GET /health-report health-report --prefetch && pass SUB-BRIDGE-PARITY "health-report" || fail SUB-BRIDGE-PARITY "health-report"
  _compare_route condition GET /condition condition && pass SUB-BRIDGE-PARITY "condition" || fail SUB-BRIDGE-PARITY "condition"
  _compare_route fetch POST /fetch fetch && pass SUB-BRIDGE-PARITY "fetch" || warn SUB-BRIDGE-PARITY "fetch skipped"
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run start >/tmp/subaru-bridge-cmd-dry.json 2>&1; then
    warn SUB-BRIDGE-COMMAND-DRY "start dry-run did not block"
  else
    pass SUB-BRIDGE-COMMAND-DRY "start blocked when actuation disabled"
  fi
else
  warn SUB-BRIDGE-PARITY "skipped — bridge not healthy"
fi

echo "=== subaru-bridge-gates (hard_fail=${FAIL}) ==="
exit "$FAIL"
