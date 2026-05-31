#!/usr/bin/env bash
# Parse Talk fast-path: [@]openclaw subaru <subcommand> [args]
# Also accepts NC mention chips: {mention-user1} subaru status
set -euo pipefail

MSG="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Preserve caller/test mention before .env reload overwrites it.
_SAVED_MENTION="${OPENCLAW_AGENT_MENTION:-}"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-agent-env.sh" 2>/dev/null || true
if [[ -n "$_SAVED_MENTION" ]]; then
  export OPENCLAW_AGENT_MENTION="$_SAVED_MENTION"
fi
MENTION="${OPENCLAW_AGENT_MENTION:-@openclaw}"
AGENT_NAME="${MENTION#@}"

if [[ -z "$MSG" ]]; then
  exit 1
fi

PY="${SUBARU_PYTHON:-python3}"
exec "$PY" "${SCRIPT_DIR}/lib/subaru_dispatch_parse.py" "$MSG" "$AGENT_NAME"
