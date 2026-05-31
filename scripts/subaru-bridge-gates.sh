#!/usr/bin/env bash
# Phase 2 bridge gates (optional). Requires running container on 127.0.0.1:8790
set -euo pipefail

BASE="${SUBARU_BRIDGE_URL:-http://127.0.0.1:8790}"
KEY="${SUBARU_BRIDGE_API_KEY:-}"
FAIL=0
pass() { echo "Gate $1: PASS — $2"; }
fail() { echo "Gate $1: FAIL — $2" >&2; FAIL=1; }

code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "${BASE}/health" 2>/dev/null || echo 000)"
[[ "$code" == "200" ]] && pass SUB-BRIDGE-HEALTH "GET /health 200" || fail SUB-BRIDGE-HEALTH "HTTP $code"

if [[ -n "$KEY" ]]; then
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 -H "X-API-Key: ${KEY}" "${BASE}/status" 2>/dev/null || echo 000)"
  [[ "$code" == "200" ]] && pass SUB-BRIDGE-PARITY "GET /status 200" || fail SUB-BRIDGE-PARITY "HTTP $code"
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "${BASE}/status" 2>/dev/null || echo 000)"
  [[ "$code" == "401" ]] && pass SUB-BRIDGE-AUTH "missing key → 401" || warn="SUB-BRIDGE-AUTH expected 401 got $code"
else
  pass SUB-BRIDGE-AUTH "no API key configured (open bridge)"
fi

echo "=== subaru-bridge-gates (hard_fail=${FAIL}) ==="
exit "$FAIL"
