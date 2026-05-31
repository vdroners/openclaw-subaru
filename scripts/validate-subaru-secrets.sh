#!/usr/bin/env bash
# Validate Subaru secret files (mode 600, required paths when enabled).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

FAIL=0
pass() { echo "Gate SUB-SEC: PASS — $1"; }
fail() { echo "Gate SUB-SEC: FAIL — $1" >&2; FAIL=1; }

if [[ "${SUBARU_ENABLED:-0}" != "1" ]]; then
  echo "Gate SUB-SEC: WARN — SUBARU_ENABLED not set (skip)"
  exit 0
fi

[[ -n "${SUBARU_USERNAME:-}" ]] || fail "SUBARU_USERNAME not set"

_check_file() {
  local label="$1" path="$2"
  path="${path/#\~/$HOME}"
  if [[ ! -f "$path" ]]; then
    fail "$label missing ($path)"
    return
  fi
  local mode
  mode="$(stat -c '%a' "$path" 2>/dev/null || echo 000)"
  if [[ "$mode" != "600" && "$mode" != "400" ]]; then
    fail "$label mode $mode (want 600)"
    return
  fi
  pass "$label present mode $mode"
}

[[ -n "${SUBARU_PASSWORD_FILE:-}" ]] && _check_file "password" "$SUBARU_PASSWORD_FILE"
[[ -n "${SUBARU_PIN_FILE:-}" ]] && _check_file "pin" "$SUBARU_PIN_FILE"

exit "$FAIL"
