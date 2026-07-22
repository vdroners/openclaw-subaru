#!/usr/bin/env bash
# Optional one-liner for family morning digest (fuel + health score).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

if [[ "${SUBARU_ENABLED:-0}" != "1" || "${SUBARU_MORNING_BRIEF:-0}" != "1" ]]; then
  exit 0
fi

summary="$(bash "${SCRIPT_DIR}/subaru-vehicle.sh" summary 2>/dev/null || echo '{}')"
TRIP_LOG="${SUBARU_TRIP_LOG:-${OPENCLAW_DIR:-${HOME}/.openclaw}/state/subaru-trips.jsonl}"
line="$(python3 - "$summary" "$TRIP_LOG" "${SCRIPT_DIR}/lib" <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[3])
from subaru_trips import parse_sample, append_sample, load_samples, weekly_digest, fuel_digest

try:
    p = json.loads(sys.argv[1])
except (json.JSONDecodeError, ValueError):
    p = {}
data = p.get("data", {}) or {}
text = data.get("summary_text", "")
first = text.split("\n")[0] if text else "no data"

# Record one trip sample/day and append a rolling weekly digest when available.
trip_log = sys.argv[2]
status = (data.get("vehicle_status") or {})
try:
    append_sample(trip_log, parse_sample(status))
    digest = weekly_digest(load_samples(trip_log))
    fuel_line = fuel_digest(load_samples(trip_log))
except OSError:
    digest = None
    fuel_line = None

line = "Subaru: " + first
if digest:
    line += " — " + digest
if fuel_line:
    line += " — " + fuel_line
print(line)
PY
)" || line="Subaru: (unavailable)"
echo "$line"
