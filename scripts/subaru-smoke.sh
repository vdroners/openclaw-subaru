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

_validate_envelope() {
  local out="$1"
  python3 - "$out" "${ROOT}/config/subaru-response.schema.json" <<'PY'
import json, sys
payload = json.load(open(sys.argv[1]))
required = json.load(open(sys.argv[2])).get("required", [])
missing = [k for k in required if k not in payload]
if missing:
    print(f"missing keys: {missing}", file=sys.stderr)
    sys.exit(1)
if "ok" not in payload or "command" not in payload or "data" not in payload:
    sys.exit(1)
PY
}

_run_dry() {
  local label="$1"
  shift
  if ! bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run "$@" >/tmp/subaru-smoke.json 2>/dev/null; then
    fail "$label dry-run"
    return 1
  fi
  if ! _validate_envelope /tmp/subaru-smoke.json; then
    fail "$label invalid envelope"
    return 1
  fi
  return 0
}

_cmds=(
  "status"
  "summary"
  "raw"
  "show"
  "capabilities"
  "health"
  "health-report"
  "condition"
  "maps-link"
  "fetch"
  "update"
  "locate"
  "charge"
)
for c in "${_cmds[@]}"; do
  _run_dry "$c" "$c" || true
done

_run_dry "presets-list" presets list || true
_run_dry "presets-show" presets show || true
_run_dry "vehicles-list" vehicles list || true
_run_dry "auth-check" auth check || true
_run_dry "pin-test" pin test || true

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run start >/tmp/subaru-smoke-start.json 2>/dev/null; then
  if python3 -c "import json; p=json.load(open('/tmp/subaru-smoke-start.json')); exit(0 if p.get('error_code')=='actuation_disabled' else 1)"; then
    pass "start blocked with actuation_disabled"
  else
    fail "start dry-run should return actuation_disabled"
  fi
else
  pass "start rejected when actuation disabled"
fi

for act_cmd in lock unlock stop horn lights; do
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run "$act_cmd" >/tmp/subaru-smoke-act.json 2>&1; then
    if python3 -c "import json; p=json.load(open('/tmp/subaru-smoke-act.json')); exit(0 if p.get('error_code')=='actuation_disabled' else 1)"; then
      pass "$act_cmd actuation_disabled"
    else
      fail "$act_cmd should return actuation_disabled"
    fi
  else
    pass "$act_cmd rejected when actuation disabled"
  fi
done

_extra_dry=(
  "auth-connect:auth connect"
  "presets-get:presets get Default"
  "vehicles-select:vehicles select example-vin-dry-run"
  "config-set:config set fetch-interval 60"
)
for spec in "${_extra_dry[@]}"; do
  label="${spec%%:*}"
  cmd="${spec#*:}"
  # shellcheck disable=SC2086
  _run_dry "$label" $cmd || true
done

pass "dry-run command envelope checks"
echo "SUBARU_SMOKE_OK"
exit "$FAIL"
