#!/usr/bin/env bash
# Cron: post Talk alert on Subaru health WARN/FAIL deltas.
# Usage: subaru-status-alert.sh [--dry-run]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

_resolve_talk_helper() {
  local name="$1"
  if [[ -x "${SCRIPT_DIR}/${name}" ]]; then
    echo "${SCRIPT_DIR}/${name}"
    return
  fi
  if [[ -n "${OPENCLAW_SKYLIGHT_ROOT:-}" && -x "${OPENCLAW_SKYLIGHT_ROOT}/scripts/${name}" ]]; then
    echo "${OPENCLAW_SKYLIGHT_ROOT}/scripts/${name}"
    return
  fi
  if [[ -x "${OPENCLAW_DIR}/scripts/${name}" ]]; then
    echo "${OPENCLAW_DIR}/scripts/${name}"
  fi
}

NC_ENV="$(_resolve_talk_helper load-nextcloud-env.sh)"
if [[ -n "$NC_ENV" ]]; then
  # shellcheck source=/dev/null
  source "$NC_ENV"
fi

DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

if [[ "${SUBARU_ENABLED:-0}" != "1" ]]; then
  echo "SUBARU_ALERT_OK disabled"
  exit 0
fi

STATE="${OPENCLAW_DIR}/state/subaru-last-alert.json"
mkdir -p "$(dirname "$STATE")"

if [[ "$DRY" -eq 1 ]]; then
  echo '{"ok":true,"data":{"verdict":"pass","score":100}}'
  echo "SUBARU_ALERT_OK dry-run"
  exit 0
fi

report="$(bash "${SCRIPT_DIR}/subaru-vehicle.sh" fetch >/dev/null 2>&1 || true)"
report="$(bash "${SCRIPT_DIR}/subaru-vehicle.sh" health-report --prefetch 2>/dev/null || echo '{}')"
verdict="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('data',{}).get('verdict','pass'))" "$report" 2>/dev/null || echo pass)"
score="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('data',{}).get('score',100))" "$report" 2>/dev/null || echo 100)"

prev_verdict="pass"
if [[ -f "$STATE" ]]; then
  prev_verdict="$(python3 -c "import json; print(json.load(open('$STATE')).get('verdict','pass'))" 2>/dev/null || echo pass)"
fi

if [[ "$verdict" == "pass" && "$prev_verdict" == "pass" ]]; then
  echo "SUBARU_ALERT_OK quiet score=${score}"
  python3 -c "import json; json.dump({'verdict': '$verdict', 'score': $score}, open('$STATE','w'))"
  exit 0
fi

ROOM="${SUBARU_ALERT_TALK_ROOM:-${SKYLIGHT_OPS_TALK_ROOM:-}}"
if [[ -z "$ROOM" ]]; then
  echo "SUBARU_ALERT_OK no room configured verdict=${verdict}"
  python3 -c "import json; json.dump({'verdict': '$verdict', 'score': $score}, open('$STATE','w'))"
  exit 0
fi

summary="$(python3 -c "
import json, sys
d = json.loads(sys.argv[1]).get('data', {})
checks = d.get('checks') or []
lines = [c.get('message','') for c in checks if c.get('status') in ('warn','fail')]
print('; '.join(lines[:5]) or f'Subaru health {d.get(\"verdict\")} score {d.get(\"score\")}')
" "$report" 2>/dev/null || echo "Subaru health ${verdict}")"

msg="SUBARU ALERT: ${summary}"
TALK_POST="$(_resolve_talk_helper talk-post.sh)"
if [[ -n "$TALK_POST" ]]; then
  SKYLIGHT_OPS_TALK_ROOM="$ROOM" bash "$TALK_POST" "$msg" >/dev/null 2>&1 || true
fi
python3 -c "import json; json.dump({'verdict': '$verdict', 'score': $score}, open('$STATE','w'))"
echo "SUBARU_ALERT_POSTED verdict=${verdict} score=${score}"
exit 0
