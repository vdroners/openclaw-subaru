#!/usr/bin/env bash
# Execute Talk fast-path: parse dispatch JSON and run subaru-vehicle.sh
# Usage: subaru-dispatch-exec.sh [--dry-run] [--sender ID] [--room TOKEN]
#          [--source talk|cli|agent|cron|router] [--message-id ID]
#          [--verified valid|unverified|...] [--allowed-room] "message"
#
# Context (also read from env when the flag is absent):
#   --sender      SUBARU_AUDIT_SENDER, else TALK_ACTOR_ID     (e.g. users/NCAdmin)
#   --room        SUBARU_AUDIT_ROOM,   else TALK_ROOM         (Talk room token)
#   --source      SUBARU_AUDIT_SOURCE  (default: talk when TALK_SOURCE is set or
#                 SUBARU_TALK_FASTPATH=1, else cli; "talk-webhook-shim" logs as talk)
#   --message-id  SUBARU_AUDIT_MESSAGE_ID, else TALK_MESSAGE_ID
#   --verified    TALK_VERIFIED (webhook signature state from the shim)
#   --allowed-room  or SUBARU_ENFORCE_ALLOWED_ROOM=1: actuation is refused unless
#                 the room equals the token held in the env var NAMED by
#                 SUBARU_ALLOWED_ROOM_VAR (default SKYLIGHT_FAMILY_TALK_ROOM).
#                 Fails closed: unset/empty token, empty room, or (source=talk)
#                 a verified state other than "valid" all refuse. The token value
#                 is never printed.
# Confirm: a verified (TALK_VERIFIED=valid) message from the Family Hub room with
# a known sender never needs the word "confirm" (Sarge, 16 Nov 2026). Calls from
# the shim (TALK_SOURCE set + SUBARU_TALK_FASTPATH=1) always get the room check.
# Every actuation attempt (refused, failed, ok) is appended to
# $OPENCLAW_DIR/state/subaru-command-log.jsonl with sender/room/source/result.
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

MENTION="${OPENCLAW_AGENT_MENTION:-@openclaw}"
AUDIT_PY="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/lib/subaru_audit.py"

DRY=0
ENFORCE_ROOM="${SUBARU_ENFORCE_ALLOWED_ROOM:-0}"
A_SENDER="${SUBARU_AUDIT_SENDER:-${TALK_ACTOR_ID:-}}"
A_ROOM="${SUBARU_AUDIT_ROOM:-${TALK_ROOM:-}}"
A_SOURCE="${SUBARU_AUDIT_SOURCE:-}"
A_MSGID="${SUBARU_AUDIT_MESSAGE_ID:-${TALK_MESSAGE_ID:-}}"
A_VERIFIED="${TALK_VERIFIED:-}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --allowed-room) ENFORCE_ROOM=1; shift ;;
    --sender) A_SENDER="${2:-}"; shift 2 ;;
    --room) A_ROOM="${2:-}"; shift 2 ;;
    --source) A_SOURCE="${2:-}"; shift 2 ;;
    --message-id) A_MSGID="${2:-}"; shift 2 ;;
    --verified) A_VERIFIED="${2:-}"; shift 2 ;;
    --) shift; break ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) break ;;
  esac
done
if [[ -z "$A_SOURCE" ]]; then
  if [[ -n "${TALK_SOURCE:-}" || "${SUBARU_TALK_FASTPATH:-0}" == "1" ]]; then A_SOURCE=talk; else A_SOURCE=cli; fi
fi
# The Talk webhook shim (talk-webhook-shim.py) exports TALK_SOURCE,
# TALK_ROOM, TALK_ACTOR_ID, TALK_MESSAGE_ID and TALK_VERIFIED to every fast-path
# child. A shim-originated call always gets the Family Hub room check.
if [[ -n "${TALK_SOURCE:-}" && "${SUBARU_TALK_FASTPATH:-0}" == "1" ]]; then
  ENFORCE_ROOM=1
fi
case "$A_SOURCE" in talk-webhook-shim|talk-shim|shim) A_SOURCE=talk ;; esac
# Hand the context to the Python core (it stamps every audit row from env).
export SUBARU_AUDIT_SENDER="$A_SENDER" SUBARU_AUDIT_ROOM="$A_ROOM" \
  SUBARU_AUDIT_SOURCE="$A_SOURCE" SUBARU_AUDIT_MESSAGE_ID="$A_MSGID"

MSG="${1:-}"
if [[ -z "$MSG" ]]; then
  echo "usage: $0 [--dry-run] [--sender ID] [--room TOKEN] [--source SRC] [--allowed-room] \"${MENTION} subaru ...\"" >&2
  exit 2
fi

# _audit_refusal <action> <error_code> [preset]
_audit_refusal() {
  local extra=()
  [[ -n "${3:-}" ]] && extra=( --preset "$3" )
  [[ "$DRY" -eq 1 ]] && extra+=( --dry-run )
  python3 "$AUDIT_PY" log --command "$1" --result refused --error-code "$2" "${extra[@]}" \
    >/dev/null 2>&1 || echo "[subaru] audit write failed" >&2
}

# _refuse <action> <error_code> <human message>
_refuse() {
  _audit_refusal "$1" "$2" "${PRESET_FOR_AUDIT:-}"
  python3 - "$1" "$2" "$3" <<'PY'
import json, sys
action, code, msg = sys.argv[1:4]
print(json.dumps({"ok": False, "error_code": code, "errors": [msg], "nickname": "Subaru", "command": action}))
PY
  exit 0
}

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
PRESET_FOR_AUDIT="$(python3 -c "import json,sys; a=json.loads(sys.argv[1]); print(a[a.index('--preset')+1] if '--preset' in a else '')" "$args_json")"
if [[ "$is_actuation" -eq 1 ]]; then
  if [[ "${SUBARU_ACTUATION_ENABLED:-0}" != "1" && "${SUBARU_FASTPATH_ACTUATION:-0}" != "1" ]]; then
    _refuse "$action" actuation_disabled "Remote ${action} is disabled. Set SUBARU_ACTUATION_ENABLED=1 after operator approval."
  fi
  # Room allowlist (Family Hub only). Fail closed; never echo the token.
  if [[ "$ENFORCE_ROOM" == "1" ]]; then
    room_var="${SUBARU_ALLOWED_ROOM_VAR:-SKYLIGHT_FAMILY_TALK_ROOM}"
    if [[ ! "$room_var" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      _refuse "$action" allowed_room_unconfigured "Car controls are locked: the allowed room is not configured."
    fi
    allowed_token="${!room_var:-}"
    if [[ -z "$allowed_token" ]]; then
      _refuse "$action" allowed_room_unconfigured "Car controls are locked: the allowed room is not configured."
    fi
    if [[ -z "$A_ROOM" || "$A_ROOM" != "$allowed_token" ]]; then
      _refuse "$action" room_not_allowed "Car controls only work from the Family Hub room."
    fi
    if [[ "$A_SOURCE" == "talk" && "$A_VERIFIED" != "valid" ]]; then
      _refuse "$action" talk_unverified "Car controls need a verified Talk message."
    fi
    if [[ "$A_SOURCE" == "talk" && -z "$A_SENDER" ]]; then
      _refuse "$action" sender_missing "Car controls need to know who asked."
    fi
  fi
  # Sarge (16 Nov 2026): no confirm step for anyone in Family Hub. A verified
  # webhook from the Family Hub room acts right away; the word "confirm" is
  # only still required for other Talk paths when SUBARU_REQUIRE_TALK_CONFIRM=1.
  fh_room_var="${SUBARU_ALLOWED_ROOM_VAR:-SKYLIGHT_FAMILY_TALK_ROOM}"
  fh_token=""
  [[ "$fh_room_var" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && fh_token="${!fh_room_var:-}"
  fh_verified=0
  if [[ "$A_VERIFIED" == "valid" && -n "$fh_token" && -n "$A_ROOM" && "$A_ROOM" == "$fh_token" && -n "$A_SENDER" ]]; then
    fh_verified=1
  fi
  # Talk fast-path: require explicit confirm unless SUBARU_FASTPATH_ACTUATION bypasses it.
  if [[ "$fh_verified" -ne 1 && "${SUBARU_TALK_FASTPATH:-0}" == "1" && "${SUBARU_REQUIRE_TALK_CONFIRM:-0}" == "1" && "${SUBARU_FASTPATH_ACTUATION:-0}" != "1" ]]; then
    if ! printf '%s' "$MSG" | grep -qiE '(^|[[:space:]])confirm($|[[:space:]])'; then
      _refuse "$action" actuation_confirm_required "Remote ${action} from Talk requires 'confirm' (e.g. ${MENTION} subaru ${action} confirm)."
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
  printf 'SUBARU_DISPATCH_DRY action=%s cmd=subaru-vehicle.sh' "$action"
  printf ' %q' "${cli_args[@]}"
  printf '\n'
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
  # The core audits API failures itself; this covers a CLI that died before
  # writing anything (crash, missing venv) so no actuation attempt goes unlogged.
  if [[ "$is_actuation" -eq 1 ]]; then
    python3 "$AUDIT_PY" log --command "$action" --result failed --error-code cli_no_output \
      ${PRESET_FOR_AUDIT:+--preset "$PRESET_FOR_AUDIT"} >/dev/null 2>&1 || true
  fi
  exit 1
fi
printf '%s\n' "$result"
