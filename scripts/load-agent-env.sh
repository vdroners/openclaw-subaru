#!/usr/bin/env bash
# Load OpenClaw agent mention alias from ~/.openclaw/.env
set -euo pipefail

OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"
ENV_FILE="${OPENCLAW_DIR}/.env"
preserve_mention="${OPENCLAW_AGENT_MENTION:-}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

if [[ -n "$preserve_mention" ]]; then
  export OPENCLAW_AGENT_MENTION="$preserve_mention"
fi
export OPENCLAW_AGENT_MENTION="${OPENCLAW_AGENT_MENTION:-@openclaw}"
