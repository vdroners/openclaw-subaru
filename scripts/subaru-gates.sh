#!/usr/bin/env bash
# Subaru gate aggregator.
# Usage: subaru-gates.sh [--check] [--live] [--actuation]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

FAIL=0
LIVE=0
ACTUATION=0
[[ "${1:-}" == "--check" ]] && shift
[[ "${1:-}" == "--live" ]] && LIVE=1 && shift
[[ "${1:-}" == "--actuation" ]] && ACTUATION=1 && shift

pass() { echo "Gate $1: PASS — $2"; }
fail() { echo "Gate $1: FAIL — $2" >&2; FAIL=1; }
warn() { echo "Gate $1: WARN — $2"; }

_json_ok() {
  python3 -c "import json,sys; p=json.load(open(sys.argv[1])); sys.exit(0 if p.get('ok') else 1)" "$1" 2>/dev/null
}

_json_field() {
  python3 - "$1" "$2" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
path = sys.argv[2].split(".")
cur = p
for k in path:
    if isinstance(cur, dict) and k in cur:
        cur = cur[k]
    else:
        cur = None
        break
if cur is None:
    print("")
elif isinstance(cur, bool):
    print(str(cur).lower())
else:
    print(cur)
PY
}

if [[ "${SUBARU_ENABLED:-0}" != "1" ]]; then
  warn SUB-SKIP "SUBARU_ENABLED not set"
  echo "=== subaru-gates summary (hard_fail=0) ==="
  exit 0
fi

bash "${SCRIPT_DIR}/validate-subaru-secrets.sh" || FAIL=1
bash "${SCRIPT_DIR}/validate-subaru-vehicle.sh" "${SUBARU_VEHICLE_JSON}" 2>/dev/null \
  || bash "${SCRIPT_DIR}/validate-subaru-vehicle.sh" "$(cd "${SCRIPT_DIR}/.." && pwd)/config/subaru-vehicle.example.json" \
  || fail SUB-X "vehicle json invalid"

if [[ -x "${SUBARU_VENV}/bin/python3" ]]; then
  if "${SUBARU_VENV}/bin/python3" -c "import subarulink" 2>/dev/null; then
    pass SUB-VENV "subarulink import ok"
  else
    fail SUB-VENV "subarulink not installed in venv"
  fi
else
  warn SUB-VENV "venv missing at ${SUBARU_VENV} (dry-run only)"
fi

_read_cmds=( status summary raw show capabilities health health-report condition maps-link fetch update locate presets-list presets-show presets-get vehicles-list vehicles-select auth-check auth-connect pin-test config-set charge )
for c in "${_read_cmds[@]}"; do
  case "$c" in
    presets-list) cli=( presets list ) ;;
    presets-show) cli=( presets show ) ;;
    presets-get) cli=( presets get Default ) ;;
    vehicles-list) cli=( vehicles list ) ;;
    vehicles-select) cli=( vehicles select "${SUBARU_VIN:-example-vin-dry-run}" ) ;;
    auth-check) cli=( auth check ) ;;
    auth-connect) cli=( auth connect ) ;;
    pin-test) cli=( pin test ) ;;
    config-set) cli=( config set fetch-interval 60 ) ;;
    *) cli=( "$c" ) ;;
  esac
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run "${cli[@]}" >/tmp/subaru-gate.out 2>&1; then
    pass "SUB-CLI-DRY" "$c dry-run ok"
  else
    fail "SUB-CLI-DRY" "$c dry-run failed"
    tail -3 /tmp/subaru-gate.out >&2 || true
  fi
done

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run start >/tmp/subaru-block.out 2>&1; then
  if grep -q actuation_disabled /tmp/subaru-block.out; then
    pass SUB-BLOCK-ACT "start blocked when actuation disabled"
  else
    warn SUB-BLOCK-ACT "expected actuation_disabled in dry-run start"
  fi
else
  pass SUB-BLOCK-ACT "start rejected when actuation disabled"
fi

_block_fail=0
for act_cmd in lock unlock stop horn lights charge; do
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run "$act_cmd" >/tmp/subaru-block-all.out 2>&1; then
    if grep -q actuation_disabled /tmp/subaru-block-all.out; then
      pass SUB-BLOCK-ACT-ALL "$act_cmd blocked"
    else
      warn SUB-BLOCK-ACT-ALL "$act_cmd expected actuation_disabled"
      _block_fail=1
    fi
  else
    pass SUB-BLOCK-ACT-ALL "$act_cmd rejected"
  fi
done
[[ "$_block_fail" -eq 1 ]] && fail SUB-BLOCK-ACT-ALL "one or more actuation cmds not blocked in dry-run"

if bash "${SCRIPT_DIR}/subaru-dispatch-exec.sh" --dry-run "${MENTION} subaru status" >/tmp/subaru-dexec.out 2>&1; then
  pass SUB-DISPATCH-EXEC-DRY "dispatch exec dry-run ok"
else
  fail SUB-DISPATCH-EXEC-DRY "$(tail -1 /tmp/subaru-dexec.out)"
fi

export SUBARU_MORNING_BRIEF=1
if bash "${SCRIPT_DIR}/subaru-morning-line.sh" >/tmp/subaru-morning.out 2>&1; then
  pass SUB-MORNING-DRY "morning line script ok"
else
  warn SUB-MORNING-DRY "morning line skipped or failed (SUBARU_ENABLED?)"
fi
unset SUBARU_MORNING_BRIEF

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run maps-link >/tmp/subaru-map-dry.out 2>&1; then
  url="$(_json_field /tmp/subaru-map-dry.out data.maps_url)"
  if [[ "$url" == https://www.google.com/maps* ]]; then
    pass SUB-MAP-DRY "maps URL format ok"
  else
    fail SUB-MAP-DRY "unexpected maps url: $url"
  fi
else
  fail SUB-MAP-DRY "maps-link dry-run failed"
fi

if bash "${SCRIPT_DIR}/subaru-status-alert.sh" --dry-run >/tmp/subaru-alert.out 2>&1; then
  grep -q SUBARU_ALERT /tmp/subaru-alert.out && pass SUB-ALERT-DRY "alert dry-run ok" || fail SUB-ALERT-DRY "missing SUBARU_ALERT line"
else
  fail SUB-ALERT-DRY "alert dry-run failed"
fi

if bash "${SCRIPT_DIR}/subaru-dispatch-test.sh" >/tmp/subaru-disp.out 2>&1; then
  pass SUB-DISPATCH "fast-path phrase matrix ok"
else
  fail SUB-DISPATCH "$(tail -1 /tmp/subaru-disp.out)"
fi

if bash "${SCRIPT_DIR}/subaru-smoke.sh" >/tmp/subaru-smoke.out 2>&1; then
  pass SUB-SMOKE "smoke ok"
else
  fail SUB-SMOKE "$(tail -1 /tmp/subaru-smoke.out)"
fi

if grep -Ei '(password|pin|Bearer)' /tmp/subaru-gate.out /tmp/subaru-alert.out 2>/dev/null | grep -qv 'actuation_disabled'; then
  fail SUB-NOSECRETS "possible secret in gate stdout"
else
  pass SUB-NOSECRETS "gate stdout clean"
fi

# Tier 1 live read gates (network, read-only)
if bash "${SCRIPT_DIR}/subaru-vehicle.sh" auth check >/tmp/subaru-auth.out 2>&1; then
  reg="$(_json_field /tmp/subaru-auth.out data.device_registered)"
  if [[ "$reg" == "True" || "$reg" == "true" || "$reg" == "1" ]]; then
    pass SUB-2FA "device registered"
  else
    warn SUB-2FA "device not registered — run subaru-auth-bootstrap.sh"
  fi
  pass SUB-AUTH "auth check ok"
else
  fail SUB-AUTH "auth check failed"
  warn SUB-2FA "bootstrap pending"
fi

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" summary >/tmp/subaru-summary.out 2>&1 && _json_ok /tmp/subaru-summary.out; then
  text="$(_json_field /tmp/subaru-summary.out data.summary_text)"
  [[ -n "$text" ]] && pass SUB-SUMMARY "summary text present" || warn SUB-SUMMARY "empty summary_text"
else
  fail SUB-SUMMARY "summary failed"
fi

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" capabilities >/tmp/subaru-cap.out 2>&1 && _json_ok /tmp/subaru-cap.out; then
  remote="$(_json_field /tmp/subaru-cap.out data.remote_status)"
  res="$(_json_field /tmp/subaru-cap.out data.res_status)"
  if [[ "$remote" == "True" || "$remote" == "true" ]] && [[ "$res" == "True" || "$res" == "true" ]]; then
    pass SUB-CAP "remote + RES available"
    pass SUB-LEVEL1 "Level 1 remote + RES entitlements"
    pass SUB-RES "remote engine start available"
  else
    warn SUB-CAP "trim may be Safety-only (remote=$remote res=$res)"
    warn SUB-LEVEL1 "Level 1 entitlements incomplete"
    warn SUB-RES "RES not available (remote=$remote res=$res)"
  fi
else
  fail SUB-CAP "capabilities failed"
fi

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" fetch >/tmp/subaru-fetch.out 2>&1 && _json_ok /tmp/subaru-fetch.out; then
  pass SUB-FETCH "fetch ok"
else
  fail SUB-FETCH "fetch failed"
fi

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" condition >/tmp/subaru-cond.out 2>&1 && _json_ok /tmp/subaru-cond.out; then
  pass SUB-CONDITION "condition ok"
else
  warn SUB-CONDITION "condition empty or failed — try after fetch"
fi

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" health >/tmp/subaru-mil.out 2>&1 && _json_ok /tmp/subaru-mil.out; then
  pass SUB-MIL "health block present"
else
  fail SUB-MIL "health failed"
fi

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" presets list >/tmp/subaru-presets.out 2>&1 && _json_ok /tmp/subaru-presets.out; then
  pass SUB-PRESETS "presets list ok"
  default_preset="$(python3 -c "import json; print(json.load(open('${SUBARU_VEHICLE_JSON}')).get('remote_start_preset',''))" 2>/dev/null || true)"
  presets_raw="$(_json_field /tmp/subaru-presets.out data.presets)"
  if [[ -n "$default_preset" && "$presets_raw" == *"$default_preset"* ]]; then
    pass SUB-PRESET-DEFAULT "default preset in list"
  elif [[ -z "$default_preset" ]]; then
    warn SUB-PRESET-DEFAULT "no remote_start_preset configured"
  else
    warn SUB-PRESET-DEFAULT "default preset '$default_preset' not in list"
  fi
else
  fail SUB-PRESETS "presets list failed"
fi

default_preset="$(python3 -c "import json; print(json.load(open('${SUBARU_VEHICLE_JSON}')).get('remote_start_preset',''))" 2>/dev/null || true)"
if [[ -n "$default_preset" ]]; then
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" presets get "$default_preset" >/tmp/subaru-pget.out 2>&1 && _json_ok /tmp/subaru-pget.out; then
    pass SUB-PRESET-GET "default preset retrievable"
  else
    warn SUB-PRESET-GET "presets get '$default_preset' failed"
  fi
fi

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" health-report --prefetch >/tmp/subaru-health.out 2>&1 && _json_ok /tmp/subaru-health.out; then
  score="$(_json_field /tmp/subaru-health.out data.score)"
  verdict="$(_json_field /tmp/subaru-health.out data.verdict)"
  if [[ -n "$score" && -n "$verdict" ]]; then
    pass SUB-HEALTH "score=$score verdict=$verdict"
  else
    fail SUB-HEALTH "missing score or verdict"
  fi
else
  fail SUB-HEALTH "health-report failed"
fi

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" status >/tmp/subaru-live-status.out 2>&1 && _json_ok /tmp/subaru-live-status.out; then
  pass SUB-STATUS "live status ok"
else
  fail SUB-STATUS "live status failed"
fi

ev="$(_json_field /tmp/subaru-cap.out data.ev)"
if [[ "$ev" == "True" || "$ev" == "true" ]]; then
  pass SUB-EV-SKIP "EV vehicle — EV gates apply"
else
  warn SUB-EV-SKIP "not EV — charge/SOC gates skipped"
fi

if [[ "${SUBARU_ACTUATION_ENABLED:-0}" == "1" ]]; then
  pass_file="${OPENCLAW_DIR}/state/subaru-gates-live-pass.json"
  require_ev=0
  [[ "$ev" == "True" || "$ev" == "true" ]] && require_ev=1
  if [[ -f "$pass_file" ]]; then
    pf="$(python3 - "$pass_file" "$require_ev" "${SCRIPT_DIR}/lib" <<'PY'
import sys
sys.path.insert(0, sys.argv[3])
from subaru_pass_file import validate_pass_file
r = validate_pass_file(sys.argv[1], require_ev_charge=sys.argv[2] == "1")
print("ok" if r["ok"] else "fail:" + ",".join(r["missing"]))
PY
)"
    if [[ "$pf" == ok ]]; then
      pass SUB-ACT-PASS-FILE "required Tier 3 gates true"
    else
      fail SUB-ACT-PASS-FILE "missing gates: ${pf#fail:}"
    fi
  else
    fail SUB-ACT-PASS-FILE "SUBARU_ACTUATION_ENABLED=1 but missing $pass_file — run subaru-record-live-pass.sh"
  fi
else
  warn SUB-ACT-PASS-FILE "actuation disabled — pass file not required"
fi

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" pin test >/tmp/subaru-pin.out 2>&1 && _json_ok /tmp/subaru-pin.out; then
  pass SUB-PIN-LIVE "pin test ok"
else
  warn SUB-PIN-LIVE "pin test failed (credentials/session?)"
fi

has_tpms="$(_json_field /tmp/subaru-cap.out data.has_tpms)"
if [[ "$has_tpms" == "True" || "$has_tpms" == "true" ]]; then
  tpms_ok=1
  for tire in TYRE_PRESSURE_FRONT_LEFT TYRE_PRESSURE_FRONT_RIGHT TYRE_PRESSURE_REAR_LEFT TYRE_PRESSURE_REAR_RIGHT; do
    val="$(_json_field /tmp/subaru-live-status.out data.vehicle_status.${tire})"
    if [[ -z "$val" || "$val" == "0" ]]; then
      tpms_ok=0
    fi
  done
  if [[ "$tpms_ok" -eq 1 ]]; then
    pass SUB-TPMS "four tire PSI present"
  else
    warn SUB-TPMS "missing TPMS values after status fetch"
  fi
else
  warn SUB-TPMS "vehicle has no TPMS capability"
fi

if bash "${SCRIPT_DIR}/subaru-vehicle.sh" maps-link >/tmp/subaru-maps-live.out 2>&1 && _json_ok /tmp/subaru-maps-live.out; then
  url="$(_json_field /tmp/subaru-maps-live.out data.maps_url)"
  [[ "$url" == https://www.google.com/maps* ]] && pass SUB-MAPS-LIVE "maps link from cache" || warn SUB-MAPS-LIVE "maps url missing"
else
  warn SUB-MAPS-LIVE "maps-link failed"
fi

audit_log="${OPENCLAW_DIR}/state/subaru-command-log.jsonl"
if [[ -f "$audit_log" ]]; then
  if grep -Ei '(password|pin|Bearer)' "$audit_log" 2>/dev/null | grep -qv 'actuation_disabled'; then
    fail SUB-CMD-LOG "possible secret in audit log"
  else
    pass SUB-CMD-LOG "audit log clean"
  fi
else
  warn SUB-AUDIT "no audit log yet (run a live command first)"
fi

if [[ "$LIVE" -eq 1 ]]; then
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" auth connect >/tmp/subaru-auth-conn.out 2>&1 && _json_ok /tmp/subaru-auth-conn.out; then
    pass SUB-AUTH-CONNECT "auth connect ok"
  else
    warn SUB-AUTH-CONNECT "auth connect failed"
  fi

  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" locate >/tmp/subaru-locate.out 2>&1 && _json_ok /tmp/subaru-locate.out; then
    lat="$(_json_field /tmp/subaru-locate.out data.lat)"
    lon="$(_json_field /tmp/subaru-locate.out data.lon)"
    if [[ -n "$lat" && -n "$lon" ]]; then
      pass SUB-LOCATE "lat/lon present"
    else
      fail SUB-LOCATE "missing coordinates"
    fi
  else
    fail SUB-LOCATE "locate failed (rate limit?)"
  fi

  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" vehicles list >/tmp/subaru-veh.out 2>&1 && _json_ok /tmp/subaru-veh.out; then
    if grep -q "${SUBARU_VIN}" /tmp/subaru-veh.out 2>/dev/null; then
      pass SUB-VEHICLES "configured VIN in list"
    else
      warn SUB-VEHICLES "VIN ${SUBARU_VIN} not found in vehicles list"
    fi
  else
    fail SUB-VEHICLES "vehicles list failed"
  fi

  stale="$(_json_field /tmp/subaru-live-status.out data.vehicle_status.staleness_seconds)"
  if [[ -n "$stale" ]]; then
    hours="$(python3 -c "print(int(float('$stale')//3600))")"
    if [[ "$hours" -gt 72 ]]; then
      fail SUB-STALE "data stale ${hours}h"
    elif [[ "$hours" -gt 24 ]]; then
      warn SUB-STALE "data stale ${hours}h"
    else
      pass SUB-STALE "data age ${hours}h"
    fi
  else
    warn SUB-STALE "staleness_seconds unavailable"
  fi

  warn SUB-UPDATE-DRY "cron must never call update — manual update gate: operator verifies once"
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" update >/tmp/subaru-update.out 2>&1 && _json_ok /tmp/subaru-update.out; then
    pass SUB-UPDATE "manual update ok"
  else
    warn SUB-UPDATE "update failed or skipped"
  fi
fi

if [[ "$ACTUATION" -eq 1 ]]; then
  echo ""
  echo "=== Tier 3 manual actuation runbook ==="
  echo "Park safely. Run each command manually and confirm vehicle response:"
  echo "  subaru-vehicle.sh lock          → SUB-LIVE-LOCK"
  echo "  subaru-vehicle.sh unlock        → SUB-LIVE-UNLOCK"
  echo "  subaru-vehicle.sh unlock --door driver → SUB-LIVE-UNLOCK-DRIVER"
  echo "  subaru-vehicle.sh start --preset <name> → SUB-LIVE-START"
  echo "  subaru-vehicle.sh stop          → SUB-LIVE-STOP"
  echo "  subaru-vehicle.sh horn / horn --stop → SUB-LIVE-HORN"
  echo "  subaru-vehicle.sh lights / lights --stop → SUB-LIVE-LIGHTS"
  echo "Then: bash scripts/subaru-record-live-pass.sh"
  echo "Then: set SUBARU_ACTUATION_ENABLED=1 in ~/.openclaw/.env"
  warn SUB-LIVE "Tier 3 is operator-manual — not automated in CI"
fi

echo ""
echo "=== subaru-gates summary (hard_fail=${FAIL}) ==="
exit "$FAIL"
