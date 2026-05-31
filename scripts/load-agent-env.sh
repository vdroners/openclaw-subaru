#!/usr/bin/env bash
# Load OpenClaw agent mention alias from ~/.openclaw/.env
set -euo pipefail

OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"
ENV_FILE="${OPENCLAW_DIR}/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

export OPENCLAW_AGENT_MENTION="${OPENCLAW_AGENT_MENTION:-@openclaw}"
