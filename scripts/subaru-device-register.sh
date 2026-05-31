#!/usr/bin/env bash
# Register this host with MySubaru 2FA (one-time). Usage:
#   bash subaru-device-register.sh 123456
#   bash subaru-device-register.sh --request          # request code, then prompt
#   bash subaru-device-register.sh --request 123456   # request + submit same session
# Do NOT re-request codes in a loop — account lockout after ~3 failures.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

REQUEST=0
CODE=""
for arg in "$@"; do
  case "$arg" in
    --request) REQUEST=1 ;;
    --help|-h)
      echo "usage: $0 [--request] [6-digit-code]" >&2
      exit 0
      ;;
    *)
      if [[ "$arg" =~ ^[0-9]{6}$ ]]; then
        CODE="$arg"
      else
        echo "usage: $0 [--request] [6-digit-code]" >&2
        exit 2
      fi
      ;;
  esac
done

args=()
[[ "$REQUEST" -eq 1 ]] && args+=(--request)
[[ -n "$CODE" ]] && args+=("$CODE")
[[ -n "$CODE" ]] && export SUBARU_DEVICE_REGISTER_CODE="$CODE"

exec "$SUBARU_PYTHON" "${SCRIPT_DIR}/lib/subaru_device_register.py" "${args[@]}"
