#!/usr/bin/env bash
# Subaru gate aggregator.
# Usage: subaru-gates.sh [--check] [--live] [--actuation]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

FAIL=0
LIVE=0
ACTUATION=0
CHECK_ONLY=1
[[ "${1:-}" == "--check" ]] && shift
[[ "${1:-}" == "--live" ]] && LIVE=1 && shift
[[ "${1:-}" == "--actuation" ]] && ACTUATION=1 && shift

pass() { echo "Gate $1: PASS — $2"; }
fail() { echo "Gate $1: FAIL — $2" >&2; FAIL=1; }
warn() { echo "Gate $1: WARN — $2"; }

if [[ "${SUBARU_ENABLED:-0}" != "1" ]]; then
  warn SUB-SKIP "SUBARU_ENABLED not set"
  echo "=== subaru-gates summary (hard_fail=0) ==="
  exit 0
fi

bash "${SCRIPT_DIR}/validate-subaru-secrets.sh" || FAIL=1
bash "${SCRIPT_DIR}/validate-subaru-vehicle.sh" "${SUBARU_VEHICLE_JSON}" 2>/dev/null \
  || bash "${SCRIPT_DIR}/validate-subaru-vehicle.sh" "$(cd "${SCRIPT_DIR}/.." && pwd)/config/subaru-vehicle.example.json" \
  || fail SUB-X "vehicle json invalid"

if [[ -x "${SUBARU_VENV}/bin/python3" ]]; then
  if "${SUBARU_VENV}/bin/python3" -c "import subarulink" 2>/dev/null; then
    pass SUB-VENV "subarulink import ok"
  else
    fail SUB-VENV "subarulink not installed in venv"
  fi
else
  warn SUB-VENV "venv missing at ${SUBARU_VENV} (dry-run only)"
fi

_read_cmds=( status summary capabilities health health-report condition maps-link presets-list vehicles-list auth-check )
for c in "${_read_cmds[@]}"; do
  case "$c" in
    presets-list) cli=( presets list ) ;;
    vehicles-list) cli=( vehicles list ) ;;
    auth-check) cli=( auth check ) ;;
    *) cli=( "$c" ) ;;
  esac
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run "${cli[@]}" >/tmp/subaru-gate.out 2>&1; then
    pass "SUB-CLI-DRY" "$c dry-run ok"
  else
    fail "SUB-CLI-DRY" "$c dry-run failed"
    tail -3 /tmp/subaru-gate.out >&2 || true
  fi
done

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run start >/tmp/subaru-block.out 2>&1; then
  if grep -q actuation_disabled /tmp/subaru-block.out; then
    pass SUB-BLOCK-ACT "start blocked when actuation disabled"
  else
    warn SUB-BLOCK-ACT "expected actuation_disabled in dry-run start"
  fi
else
  pass SUB-BLOCK-ACT "start rejected when actuation disabled"
fi

if bash "${SCRIPT_DIR}/subaru-status-alert.sh" --dry-run >/tmp/subaru-alert.out 2>&1; then
  grep -q SUBARU_ALERT /tmp/subaru-alert.out && pass SUB-ALERT-DRY "alert dry-run ok" || fail SUB-ALERT-DRY "missing SUBARU_ALERT line"
else
  fail SUB-ALERT-DRY "alert dry-run failed"
fi

if bash "${SCRIPT_DIR}/subaru-dispatch.sh" '@openclaw subaru status' >/tmp/subaru-disp.out 2>&1; then
  pass SUB-DISPATCH "status parse ok"
else
  fail SUB-DISPATCH "dispatch failed"
fi

if bash "${SCRIPT_DIR}/subaru-smoke.sh" >/tmp/subaru-smoke.out 2>&1; then
  pass SUB-SMOKE "smoke ok"
else
  fail SUB-SMOKE "$(tail -1 /tmp/subaru-smoke.out)"
fi

if grep -Ei '(password|pin|Bearer)' /tmp/subaru-gate.out /tmp/subaru-alert.out 2>/dev/null | grep -qv 'actuation_disabled'; then
  fail SUB-NOSECRETS "possible secret in gate stdout"
else
  pass SUB-NOSECRETS "gate stdout clean"
fi

if [[ "$LIVE" -eq 1 ]]; then
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" status >/tmp/subaru-live-status.out 2>&1; then
    pass SUB-STATUS "live status ok"
  else
    fail SUB-STATUS "live status failed"
  fi
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" pin test >/tmp/subaru-pin.out 2>&1; then
    pass SUB-PIN-LIVE "pin test ok"
  else
    warn SUB-PIN-LIVE "pin test failed (credentials/session?)"
  fi
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" auth check >/tmp/subaru-auth.out 2>&1; then
    pass SUB-AUTH "auth check ok"
  else
    fail SUB-AUTH "auth check failed"
  fi
fi

if [[ "$ACTUATION" -eq 1 ]]; then
  warn SUB-LIVE "manual actuation gates — operator must verify lock/unlock/start/stop in safe context"
fi

echo ""
echo "=== subaru-gates summary (hard_fail=${FAIL}) ==="
exit "$FAIL"
