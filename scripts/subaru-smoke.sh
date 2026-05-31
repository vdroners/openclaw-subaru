#!/usr/bin/env bash
# Publish-safe Subaru smoke (dry-run only, no credentials required).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export SUBARU_DRY_RUN=1
export SUBARU_ENABLED=0

pass() { echo "Gate SUB-SMOKE: PASS — $1"; }
fail() { echo "Gate SUB-SMOKE: FAIL — $1" >&2; FAIL=1; }

FAIL=0

bash "${SCRIPT_DIR}/validate-subaru-vehicle.sh" "${ROOT}/config/subaru-vehicle.example.json" || FAIL=1

if ! python3 - "${ROOT}/config/subaru-response.schema.json" "${ROOT}/tests/subaru/fixtures/status_ok.json" <<'PY'
import json, sys
from pathlib import Path
schema = json.load(open(sys.argv[1]))
fixture = json.load(open(sys.argv[2]))
required = schema.get("required", [])
missing = [k for k in required if k not in fixture]
if missing:
    print(f"Gate X-SUB-OUT: FAIL — fixture missing {missing}", file=sys.stderr)
    sys.exit(1)
print("Gate X-SUB-OUT: PASS — response fixture valid")
PY
then
  FAIL=1
fi

_cmds=(
  "status"
  "summary"
  "capabilities"
  "health"
  "health-report"
  "condition"
  "maps-link"
  "fetch"
  "locate"
)
for c in "${_cmds[@]}"; do
  if ! bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run "$c" >/tmp/subaru-smoke.json 2>/dev/null; then
    fail "$c dry-run"
    continue
  fi
  if ! python3 - /tmp/subaru-smoke.json <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
assert "ok" in p and "command" in p and "data" in p
PY
  then
    fail "$c invalid envelope"
  fi
done

pass "dry-run command envelope checks"
echo "SUBARU_SMOKE_OK"
exit "$FAIL"
