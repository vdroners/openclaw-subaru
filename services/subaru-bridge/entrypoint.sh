#!/usr/bin/env bash
# Load file-based secrets into env for subaru-bridge container.
set -euo pipefail

_read() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  cat "$f"
}

if [[ -n "${SUBARU_PASSWORD_FILE:-}" && -z "${SUBARU_PASSWORD:-}" ]]; then
  export SUBARU_PASSWORD="$(_read "${SUBARU_PASSWORD_FILE/#\~/$HOME}")"
fi
if [[ -n "${SUBARU_PIN_FILE:-}" && -z "${SUBARU_PIN:-}" ]]; then
  export SUBARU_PIN="$(_read "${SUBARU_PIN_FILE/#\~/$HOME}")"
fi
if [[ -n "${SUBARU_BRIDGE_KEY_FILE:-}" && -z "${SUBARU_BRIDGE_API_KEY:-}" ]]; then
  export SUBARU_BRIDGE_API_KEY="$(_read "${SUBARU_BRIDGE_KEY_FILE/#\~/$HOME}")"
fi

exec "$@"
