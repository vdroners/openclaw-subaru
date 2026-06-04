#!/usr/bin/env bash
# Run Subaru Talk dispatch + formatter + talk-post (no LLM).
# Usage: subaru-talk-fast-path.sh "message text" room_token
set -euo pipefail

MSG="${1:-}"
ROOM="${2:-}"
if [[ -z "$MSG" || -z "$ROOM" ]]; then
  echo "usage: $0 \"<message>\" <room_token>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-agent-env.sh" 2>/dev/null || true
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

# Tell dispatch-exec it is serving a Talk reply: enables the richer summary
# deck and staleness-gated refresh before reporting telemetry to the operator.
export SUBARU_TALK_FASTPATH=1

dispatch="${SCRIPT_DIR}/subaru-dispatch-exec.sh"
formatter="${SCRIPT_DIR}/subaru-format-talk-reply.sh"
talk_post="${HOME}/.openclaw/scripts/talk-post.sh"
if [[ ! -x "$talk_post" ]]; then
  talk_post="${HOME}/openclaw-skylight/scripts/talk-post.sh"
fi
if [[ ! -x "$talk_post" ]]; then
  echo "subaru-talk-fast-path: talk-post.sh not found" >&2
  exit 1
fi

# Never pass tool JSON blobs to dispatch; extract operator text first.
clean_msg="$("$SUBARU_PYTHON" - "$MSG" "$SCRIPT_DIR" <<'PY'
import sys
from pathlib import Path
script_dir = Path(sys.argv[2])
sys.path.insert(0, str(script_dir / "lib"))
from subaru_talk_match import extract_user_message, is_tool_json_payload
raw = sys.argv[1]
if is_tool_json_payload(raw):
    sys.exit(2)
print(extract_user_message(raw))
PY
)" || {
  echo "subaru-talk-fast-path: ignored tool JSON payload" >&2
  exit 0
}

result="$(bash "$dispatch" "$clean_msg" 2>/dev/null)" || result=""
if [[ -z "$result" ]]; then
  summary="Subaru: could not parse that command. Try: @openclaw subaru status"
elif ! printf '%s' "$result" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
  summary="Subaru: command failed."
else
  summary="$(printf '%s' "$result" | bash "$formatter" 2>/dev/null || true)"
fi
if [[ -z "$summary" ]]; then
  summary="Subaru: command failed. Try: @openclaw subaru status"
fi
summary="$(printf '%s' "$summary" | grep -v '^SUBARU_' | head -c 500 | sed '/./,$!d')"
bash "$talk_post" "$summary" "$ROOM"
echo "subaru-talk-fast-path: ok room=$ROOM chars=${#summary}"
