#!/usr/bin/env bash
# Execute Talk fast-path: parse dispatch JSON and run subaru-vehicle.sh
# Usage: subaru-dispatch-exec.sh [--dry-run] "message"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-agent-env.sh" 2>/dev/null || true

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
fi

mapfile -t cli_args < <(python3 - "$action" "$args_json" <<'PY'
import json, sys
action = sys.argv[1]
args = json.loads(sys.argv[2])
out = [action]
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

bash "${SCRIPT_DIR}/subaru-vehicle.sh" "${bridge[@]}" "${cli_args[@]}"
