#!/usr/bin/env bash
# Cron: scheduled remote engine start / climate preconditioning.
# Schedule the time with cron (e.g. weekday 06:50); this wrapper handles the
# enable gates, preset resolution, optional weekday filter, and Talk confirmation.
#
# Usage: subaru-scheduled-start.sh [--dry-run] [--preset NAME]
#
# Gates (all must hold to actuate):
#   SUBARU_ENABLED=1               integration on
#   SUBARU_SCHEDULED_START=1       this feature opted in
#   SUBARU_ACTUATION_ENABLED=1     remote actuation allowed (start is Tier 2)
# Optional:
#   SUBARU_SCHEDULED_START_DAYS    space list of 3-letter days, e.g. "Mon Tue Wed Thu Fri"
#   SUBARU_SCHEDULED_START_PRESET  preset name (else --preset, else config default)
#   SUBARU_SCHEDULED_START_ROOM    Talk room for a confirmation post
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

DRY=0
PRESET=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --preset) PRESET="${2:-}"; shift ;;
    --preset=*) PRESET="${1#*=}" ;;
  esac
  shift
done

[[ -z "$PRESET" ]] && PRESET="${SUBARU_SCHEDULED_START_PRESET:-}"

# Optional weekday filter (cron may already constrain this; this is a safety net).
if [[ -n "${SUBARU_SCHEDULED_START_DAYS:-}" ]]; then
  today="$(date +%a)"
  case " ${SUBARU_SCHEDULED_START_DAYS} " in
    *" ${today} "*) : ;;
    *)
      echo "SUBARU_SCHED_SKIP day=${today} not in [${SUBARU_SCHEDULED_START_DAYS}]"
      exit 0
      ;;
  esac
fi

start_args=( start )
if [[ -n "$PRESET" ]]; then
  start_args=( start --preset "$PRESET" )
fi

if [[ "$DRY" -eq 1 ]]; then
  if [[ "${SUBARU_ACTUATION_ENABLED:-0}" != "1" ]]; then
    echo "SUBARU_SCHED_DRY blocked=actuation_disabled cmd=subaru-vehicle.sh ${start_args[*]}"
  else
    echo "SUBARU_SCHED_DRY cmd=subaru-vehicle.sh ${start_args[*]}"
  fi
  exit 0
fi

if [[ "${SUBARU_ENABLED:-0}" != "1" || "${SUBARU_SCHEDULED_START:-0}" != "1" ]]; then
  echo "SUBARU_SCHED_OK disabled (SUBARU_SCHEDULED_START!=1)"
  exit 0
fi

if [[ "${SUBARU_ACTUATION_ENABLED:-0}" != "1" ]]; then
  echo "SUBARU_SCHED_SKIP actuation_disabled"
  exit 0
fi

result="$(bash "${SCRIPT_DIR}/subaru-vehicle.sh" "${start_args[@]}" 2>/dev/null || echo '{}')"
ok="$(python3 -c "import json,sys; print('1' if json.loads(sys.argv[1]).get('ok') else '0')" "$result" 2>/dev/null || echo 0)"

ROOM="${SUBARU_SCHEDULED_START_ROOM:-${SUBARU_ALERT_TALK_ROOM:-}}"
if [[ -n "$ROOM" ]]; then
  talk_post=""
  for cand in "${SCRIPT_DIR}/talk-post.sh" "${OPENCLAW_DIR:-${HOME}/.openclaw}/scripts/talk-post.sh"; do
    [[ -x "$cand" ]] && talk_post="$cand" && break
  done
  if [[ -n "$talk_post" ]]; then
    if [[ "$ok" == "1" ]]; then
      msg="Subaru: scheduled remote start sent${PRESET:+ (preset ${PRESET})}."
    else
      msg="Subaru: scheduled remote start FAILED — check MySubaru."
    fi
    SKYLIGHT_OPS_TALK_ROOM="$ROOM" bash "$talk_post" "$msg" "$ROOM" >/dev/null 2>&1 || true
  fi
fi

if [[ "$ok" == "1" ]]; then
  echo "SUBARU_SCHED_POSTED started preset=${PRESET:-default}"
  exit 0
fi
echo "SUBARU_SCHED_FAIL start did not confirm"
exit 1
