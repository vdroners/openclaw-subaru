#!/usr/bin/env bash
# Health scorecard wrapper.
# Usage: subaru-health-report.sh [--dry-run] [--prefetch]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY=()
PREF=()
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY=( --dry-run ) ;;
    --prefetch) PREF=( --prefetch ) ;;
  esac
done

out="$(bash "${SCRIPT_DIR}/subaru-vehicle.sh" "${DRY[@]}" health-report "${PREF[@]}")"
echo "$out"
verdict="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('data',{}).get('verdict','pass'))" "$out" 2>/dev/null || echo pass)"
case "$verdict" in
  fail) echo "SUBARU_HEALTH_FAIL"; exit 1 ;;
  warn) echo "SUBARU_HEALTH_WARN"; exit 0 ;;
  *) echo "SUBARU_HEALTH_OK"; exit 0 ;;
esac
