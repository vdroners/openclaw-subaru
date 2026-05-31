#!/usr/bin/env bash
# Load Subaru / MySubaru env from ~/.openclaw/.env and secret files.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"
ROOT="${OPENCLAW_SUBARU_ROOT:-}"

# Preserve gate/smoke overrides before .env reload (explicit 0 must win).
_preserve_actuation="${SUBARU_ACTUATION_ENABLED-__unset__}"
_preserve_enabled="${SUBARU_ENABLED-__unset__}"

if [[ -z "$ROOT" && -d "${SCRIPT_DIR}/../config" ]]; then
  ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

ENV_FILE="${OPENCLAW_DIR}/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

if [[ -n "$ROOT" && -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "${ROOT}/.env"
  set +a
fi

_read_secret() {
  local path="$1"
  [[ -n "$path" ]] || return 0
  path="${path/#\~/$HOME}"
  [[ -f "$path" ]] || return 0
  cat "$path"
}

export OPENCLAW_DIR
export OPENCLAW_SUBARU_ROOT="${ROOT:-$OPENCLAW_DIR}"
export SUBARU_ENABLED="${SUBARU_ENABLED:-0}"
export SUBARU_USERNAME="${SUBARU_USERNAME:-}"
export SUBARU_COUNTRY="${SUBARU_COUNTRY:-USA}"
export SUBARU_VIN="${SUBARU_VIN:-}"
export SUBARU_VENV="${SUBARU_VENV:-${OPENCLAW_DIR}/venv-subaru}"
export SUBARU_VEHICLE_JSON="${SUBARU_VEHICLE_JSON:-${OPENCLAW_DIR}/config/subaru-vehicle.json}"
export SUBARU_CONFIG_FILE="${SUBARU_CONFIG_FILE:-${HOME}/.subarulink.cfg}"
export SUBARU_ACTUATION_ENABLED="${SUBARU_ACTUATION_ENABLED:-0}"
export SUBARU_LOCATE_MIN_INTERVAL_H="${SUBARU_LOCATE_MIN_INTERVAL_H:-2}"
export SUBARU_ALERT_MIN_INTERVAL_H="${SUBARU_ALERT_MIN_INTERVAL_H:-6}"
export SUBARU_ALERT_TALK_ROOM="${SUBARU_ALERT_TALK_ROOM:-}"
export SUBARU_MORNING_BRIEF="${SUBARU_MORNING_BRIEF:-0}"
export SUBARU_BRIDGE_URL="${SUBARU_BRIDGE_URL:-}"

if [[ -z "${SUBARU_BRIDGE_API_KEY:-}" && -n "${SUBARU_BRIDGE_KEY_FILE:-}" ]]; then
  SUBARU_BRIDGE_API_KEY="$(_read_secret "$SUBARU_BRIDGE_KEY_FILE")"
  export SUBARU_BRIDGE_API_KEY
fi

if [[ -z "${SUBARU_PASSWORD:-}" && -n "${SUBARU_PASSWORD_FILE:-}" ]]; then
  SUBARU_PASSWORD="$(_read_secret "$SUBARU_PASSWORD_FILE")"
  export SUBARU_PASSWORD
fi
if [[ -z "${SUBARU_PIN:-}" && -n "${SUBARU_PIN_FILE:-}" ]]; then
  SUBARU_PIN="$(_read_secret "$SUBARU_PIN_FILE")"
  export SUBARU_PIN
fi

SUBARU_PYTHON="${SUBARU_VENV}/bin/python3"
if [[ ! -x "$SUBARU_PYTHON" ]]; then
  SUBARU_PYTHON="$(command -v python3)"
fi
export SUBARU_PYTHON

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-agent-env.sh" 2>/dev/null || true

if [[ "$_preserve_enabled" != "__unset__" ]]; then
  export SUBARU_ENABLED="$_preserve_enabled"
fi
if [[ "$_preserve_actuation" != "__unset__" ]]; then
  export SUBARU_ACTUATION_ENABLED="$_preserve_actuation"
fi
