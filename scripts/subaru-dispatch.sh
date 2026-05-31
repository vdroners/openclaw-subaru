#!/usr/bin/env bash
# Parse Talk fast-path: @openclaw subaru <subcommand> [args]
set -euo pipefail

MSG="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-agent-env.sh" 2>/dev/null || true
MENTION="${OPENCLAW_AGENT_MENTION:-@openclaw}"
MENTION_RE="${MENTION/@/}"

if ! echo "$MSG" | grep -qiE "@${MENTION_RE}[[:space:]]+subaru"; then
  exit 1
fi

rest="$(echo "$MSG" | sed -E "s/(?i)@${MENTION_RE}[[:space:]]+subaru[[:space:]]*//")"
sub="$(echo "$rest" | awk '{print tolower($1)}')"
arg2="$(echo "$rest" | awk '{print $2}')"
arg3="$(echo "$rest" | awk '{print $3}')"

action="status"
case "$sub" in
  status|summary|health|locate|maps|maps-link|condition|capabilities|fetch|presets|lock|unlock|stop|horn|lights|charge|start)
    action="$sub"
    ;;
  maps) action="maps-link" ;;
  health-report|health) action="health" ;;
  "") action="status" ;;
  *) action="$sub" ;;
esac

python3 - "$action" "$arg2" "$arg3" <<'PY'
import json, sys
action = sys.argv[1]
arg2 = sys.argv[2]
arg3 = sys.argv[3]
args = []
if action == "start" and arg2:
    args = ["--preset", arg2]
elif action == "unlock" and arg2 in ("driver", "drivers", "tailgate", "all"):
    args = ["--door", arg2]
elif action == "unlock" and arg2 and arg3:
    args = ["--door", arg3]
print(json.dumps({"action": action, "args": args}))
PY
exit 0
