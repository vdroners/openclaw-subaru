#!/usr/bin/env bash
# Cron: post Talk alert on Subaru health WARN/FAIL deltas.
# Usage: subaru-status-alert.sh [--dry-run] [--would-post]
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
WOULD_POST=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=1 ;;
    --would-post) WOULD_POST=1 ;;
  esac
done

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
prev_score=100
state_json="{}"
if [[ -f "$STATE" ]]; then
  state_json="$(cat "$STATE")"
  prev_verdict="$(python3 -c "import json; print(json.load(open('$STATE')).get('verdict','pass'))" 2>/dev/null || echo pass)"
  prev_score="$(python3 -c "import json; print(json.load(open('$STATE')).get('score',100))" 2>/dev/null || echo 100)"
fi

if [[ "$verdict" == "pass" && "$prev_verdict" == "pass" ]]; then
  echo "SUBARU_ALERT_OK quiet score=${score}"
  python3 -c "import json; d=json.load(open('$STATE')) if __import__('pathlib').Path('$STATE').is_file() else {}; d.update({'verdict': '$verdict', 'score': $score}); json.dump(d, open('$STATE','w'))"
  exit 0
fi

dedup="$(python3 - "$STATE" "$verdict" "$score" "$prev_verdict" "$prev_score" "${SUBARU_ALERT_MIN_INTERVAL_H:-6}" "${SCRIPT_DIR}/lib" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[7])
from subaru_alert import should_post_alert
state_path = Path(sys.argv[1])
state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
ok, reason = should_post_alert(
    state,
    verdict=sys.argv[2],
    score=float(sys.argv[3]),
    prev_verdict=sys.argv[4],
    prev_score=float(sys.argv[5]),
    min_interval_h=float(sys.argv[6]),
)
print(f"{int(ok)}:{reason}")
PY
)"

should_post="${dedup%%:*}"
dedup_reason="${dedup#*:}"

if [[ "$WOULD_POST" -eq 1 ]]; then
  if [[ "$should_post" == "1" ]]; then
    echo "SUBARU_ALERT_WOULD_POST yes reason=${dedup_reason}"
    exit 0
  fi
  echo "SUBARU_ALERT_WOULD_POST no reason=${dedup_reason}"
  exit 1
fi

if [[ "$should_post" != "1" ]]; then
  echo "SUBARU_ALERT_SKIP dedup reason=${dedup_reason} verdict=${verdict}"
  python3 -c "import json; d=json.load(open('$STATE')) if __import__('pathlib').Path('$STATE').is_file() else {}; d.update({'verdict': '$verdict', 'score': $score}); json.dump(d, open('$STATE','w'))"
  exit 0
fi

ROOM="${SUBARU_ALERT_TALK_ROOM:-${SKYLIGHT_OPS_TALK_ROOM:-}}"
if [[ -z "$ROOM" ]]; then
  echo "SUBARU_ALERT_OK no room configured verdict=${verdict}"
  python3 -c "import json; d=json.load(open('$STATE')) if __import__('pathlib').Path('$STATE').is_file() else {}; d.update({'verdict': '$verdict', 'score': $score}); json.dump(d, open('$STATE','w'))"
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
python3 -c "import json; d=json.load(open('$STATE')) if __import__('pathlib').Path('$STATE').is_file() else {}; d.update({'verdict': '$verdict', 'score': $score, 'last_post_ts': '$(date -u +%Y-%m-%dT%H:%M:%SZ)'}); json.dump(d, open('$STATE','w'))"
echo "SUBARU_ALERT_POSTED verdict=${verdict} score=${score}"
exit 0
