#!/usr/bin/env bash
# Execute Talk fast-path: parse dispatch JSON and run subaru-vehicle.sh
# Usage: subaru-dispatch-exec.sh [--dry-run] "message"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SAVED_MENTION="${OPENCLAW_AGENT_MENTION:-}"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-agent-env.sh" 2>/dev/null || true
if [[ -n "$_SAVED_MENTION" ]]; then
  export OPENCLAW_AGENT_MENTION="$_SAVED_MENTION"
fi

DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1 && shift

MSG="${1:-}"
if [[ -z "$MSG" ]]; then
  echo "usage: $0 [--dry-run] \"@openclaw subaru ...\"" >&2
  exit 2
fi

if ! parsed="$(bash "${SCRIPT_DIR}/subaru-dispatch.sh" "$MSG" 2>/dev/null)"; then
  exit 1
fi

action="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['action'])" "$parsed")"
args_json="$(python3 -c "import json,sys; print(json.dumps(json.loads(sys.argv[1]).get('args',[])))" "$parsed")"

# Talk fast-path: bare "subaru status" should render the richer summary deck
# (odometer, range, position, data age) instead of the thin status payload.
if [[ "${SUBARU_TALK_FASTPATH:-0}" == "1" && "$action" == "status" ]]; then
  action="summary"
fi

ACTUATION_CMDS="lock unlock start stop horn lights charge"
case " $ACTUATION_CMDS " in
  *" $action "*) is_actuation=1 ;;
  *) is_actuation=0 ;;
esac
if [[ "$is_actuation" -eq 1 ]]; then
  if [[ "${SUBARU_ACTUATION_ENABLED:-0}" != "1" && "${SUBARU_FASTPATH_ACTUATION:-0}" != "1" ]]; then
    python3 - "$action" <<'PY'
import json, sys
action = sys.argv[1]
print(json.dumps({
    "ok": False,
    "error_code": "actuation_disabled",
    "errors": [f"Remote {action} is disabled. Set SUBARU_ACTUATION_ENABLED=1 after operator approval."],
    "nickname": "Subaru",
}))
PY
    exit 0
  fi
  # Talk fast-path: require explicit confirm unless SUBARU_FASTPATH_ACTUATION bypasses it.
  if [[ "${SUBARU_TALK_FASTPATH:-0}" == "1" && "${SUBARU_REQUIRE_TALK_CONFIRM:-0}" == "1" && "${SUBARU_FASTPATH_ACTUATION:-0}" != "1" ]]; then
    if ! printf '%s' "$MSG" | grep -qiE '(^|[[:space:]])confirm($|[[:space:]])'; then
      python3 - "$action" <<'PY'
import json, sys
action = sys.argv[1]
print(json.dumps({
    "ok": False,
    "error_code": "actuation_confirm_required",
    "errors": [f"Remote {action} from Talk requires 'confirm' (e.g. @openclaw subaru {action} confirm)."],
    "nickname": "Subaru",
}))
PY
      exit 0
    fi
  fi
fi

mapfile -t cli_args < <(python3 - "$action" "$args_json" <<'PY'
import json, sys
action = sys.argv[1]
args = json.loads(sys.argv[2])
out = []
# A leading "--vin <VIN>" must precede the subcommand (top-level CLI option).
if len(args) >= 2 and args[0] == "--vin":
    out.extend(["--vin", args[1]])
    args = args[2:]
out.append(action)
if action == "start" and len(args) >= 2 and args[0] == "--preset":
    out.extend(args)
elif action == "unlock" and len(args) >= 2 and args[0] == "--door":
    out.extend(args)
print("\n".join(out))
PY
)

if [[ "$DRY" -eq 1 ]]; then
  echo "SUBARU_DISPATCH_DRY action=${action} cmd=subaru-vehicle.sh ${cli_args[*]}"
  exit 0
fi

bridge=()
if [[ -n "${SUBARU_BRIDGE_URL:-}" ]]; then
  bridge=( --bridge )
fi

_run_cli() {
  bash "${SCRIPT_DIR}/subaru-vehicle.sh" "${bridge[@]}" "${cli_args[@]}" 2>/dev/null
}

_staleness_seconds() {
  python3 -c '
import json, sys
try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)
data = payload.get("data") or {}
for source in (data.get("meta") or {}, data.get("vehicle_status") or {}, data):
    if isinstance(source, dict):
        val = source.get("staleness_seconds")
        if isinstance(val, (int, float)):
            print(val)
            break
'
}

# Staleness-gated refresh: Talk reads must reflect live telemetry, not a cache
# that can be hours old. Probe once; if stale, run a single update and re-read.
READ_REFRESH_CMDS="status summary condition health-report"
case " $READ_REFRESH_CMDS " in
  *" $action "*) is_read_refresh=1 ;;
  *) is_read_refresh=0 ;;
esac

result="$(_run_cli)" || result=""

if [[ "${SUBARU_TALK_FASTPATH:-0}" == "1" && "$is_read_refresh" -eq 1 && -n "$result" ]]; then
  max_age="${SUBARU_TALK_REFRESH_MAX_AGE_S:-300}"
  stale="$(printf '%s' "$result" | _staleness_seconds)"
  if [[ -n "$stale" ]] && awk "BEGIN{exit !($stale > $max_age)}"; then
    echo "[fast-path] refresh stale=${stale%.*}s > ${max_age}s -> update" >&2
    # Coalesce the automatic refresh: SUBARU_UPDATE_MIN_INTERVAL_S makes the core
    # record each update attempt and skip (serve cached) when another Talk poll
    # arrives inside the window. This stops a rate-limited update from letting the
    # next message immediately re-hammer the MySubaru endpoint. Explicit operator
    # "subaru update" requests are NOT scoped here, so they still force a refresh.
    refresh_window="${SUBARU_UPDATE_MIN_INTERVAL_S:-$max_age}"
    if SUBARU_UPDATE_MIN_INTERVAL_S="$refresh_window" \
        bash "${SCRIPT_DIR}/subaru-vehicle.sh" "${bridge[@]}" update >/dev/null 2>&1; then
      fresh="$(_run_cli)" || fresh=""
      [[ -n "$fresh" ]] && result="$fresh"
    else
      echo "[fast-path] update failed; serving cached data" >&2
    fi
  fi
fi

if [[ -z "$result" ]]; then
  exit 1
fi
printf '%s\n' "$result"
