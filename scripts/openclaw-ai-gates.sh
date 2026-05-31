#!/usr/bin/env bash
# OpenClaw AI-layer gates for Subaru shell-direct cron (CAP-SUB).
# Usage: openclaw-ai-gates.sh --check
set -euo pipefail

OPENCLAW="${OPENCLAW_DIR:-$HOME/.openclaw}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh" 2>/dev/null || true
RUNS="${OPENCLAW}/cron/runs"
MANIFEST="${OPENCLAW}/workspace/references/cron-shell-direct.yaml"
JOBS_JSON="${OPENCLAW}/cron/jobs.json"
HARD_FAIL=0
SOFT_FAIL=0

ok() { echo "PASS $*"; }
bad() { echo "FAIL $*" >&2; HARD_FAIL=$((HARD_FAIL + 1)); }
warn() { echo "WARN $*" >&2; SOFT_FAIL=$((SOFT_FAIL + 1)); }

last_run_status() {
  local job_id="$1"
  local log="${RUNS}/${job_id}.jsonl"
  [[ -f "$log" ]] || { echo "missing"; return; }
  python3 - "$log" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
if not lines:
    print("missing"); raise SystemExit
print(json.loads(lines[-1]).get("status", "unknown"))
PY
}

last_run_age_hours() {
  local job_id="$1"
  local log="${RUNS}/${job_id}.jsonl"
  [[ -f "$log" ]] || { echo "999999"; return; }
  python3 - "$log" <<'PY'
import json, sys, time
from pathlib import Path
p = Path(sys.argv[1])
lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
if not lines:
    print(999999); raise SystemExit
ts = json.loads(lines[-1]).get("ts") or json.loads(lines[-1]).get("runAtMs") or 0
print(int((time.time()*1000 - ts) / 3600000))
PY
}

check_job() {
  local gate_id="$1"
  local job_id="$2"
  local max_age_h="${3:-48}"
  local st
  st="$(last_run_status "$job_id")"
  local age
  age="$(last_run_age_hours "$job_id")"
  if [[ "$st" == "ok" && "$age" -le "$max_age_h" ]]; then
    ok "${gate_id} ${job_id} status=ok age=${age}h"
  else
    bad "${gate_id} ${job_id} status=${st} age=${age}h (max ${max_age_h}h)"
  fi
}

[[ "${1:-}" == "--check" ]] || { echo "usage: $0 --check" >&2; exit 2; }

if [[ "${SUBARU_ENABLED:-0}" == "1" ]]; then
  check_job CAP-SUB b2c3d4e5-subaru-status-alert 24
else
  warn "CAP-SUB skipped (SUBARU_ENABLED not set)"
fi

if [[ -f "$MANIFEST" && -f "$JOBS_JSON" ]]; then
  python3 - "$MANIFEST" "$JOBS_JSON" <<'PY' | while read -r line; do
import json, sys
from pathlib import Path
try:
    import yaml
except ImportError:
    raise SystemExit(0)
manifest = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
jobs = json.loads(Path(sys.argv[2]).read_text()).get("jobs", [])
by_id = {j["id"]: j for j in jobs}
for row in manifest.get("jobs", []):
    jid = row["id"]
    j = by_id.get(jid)
    if not j:
        print(f"WARN AI-CRON-4 missing openclaw job {jid}")
        continue
    if j.get("enabled", True):
        print(f"FAIL AI-CRON-4 {row['name']} still enabled in OpenClaw cron (should be shell-direct only)")
    else:
        print(f"PASS AI-CRON-4 {row['name']} disabled in OpenClaw cron")
PY
    case "$line" in
      PASS*) ok "${line#PASS }" ;;
      FAIL*) bad "${line#FAIL }" ;;
      WARN*) warn "${line#WARN }" ;;
    esac
  done
else
  warn "AI-CRON-4 skipped (manifest or jobs.json missing)"
fi

# SUB-CRON-DEDUP: alert state should respect min interval between posts
ALERT_STATE="${OPENCLAW}/state/subaru-last-alert.json"
if [[ -f "$ALERT_STATE" ]]; then
  while read -r line; do
    case "$line" in
      PASS*) ok "${line#PASS }" ;;
      WARN*) warn "${line#WARN }" ;;
      FAIL*) bad "${line#FAIL }" ;;
    esac
  done < <(python3 - "$ALERT_STATE" "${SUBARU_ALERT_MIN_INTERVAL_H:-6}" <<'PY'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
p = Path(sys.argv[1])
min_h = float(sys.argv[2])
data = json.loads(p.read_text(encoding="utf-8"))
posted = data.get("last_post_ts")
if not posted:
    print("PASS SUB-CRON-DEDUP no recent post timestamp")
    raise SystemExit
try:
    ts = datetime.fromisoformat(str(posted).replace("Z", "+00:00"))
except ValueError:
    print("WARN SUB-CRON-DEDUP unreadable last_post_ts")
    raise SystemExit
age_h = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds() / 3600.0
if age_h < min_h:
    print(f"WARN SUB-CRON-DEDUP last post {age_h:.1f}h ago (< {min_h}h min interval)")
else:
    print(f"PASS SUB-CRON-DEDUP last post {age_h:.1f}h ago")
PY
)
else
  ok "SUB-CRON-DEDUP no alert state file"
fi

echo ""
echo "=== openclaw-ai-gates summary (hard_fail=${HARD_FAIL} soft_fail=${SOFT_FAIL}) ==="
exit "$HARD_FAIL"
