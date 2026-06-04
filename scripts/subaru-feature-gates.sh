#!/usr/bin/env bash
# Offline (dry-run) pass/fail gates for the v1.1 feature + hardening surface.
# CI-safe: no credentials, no network. Wired into publish-gates.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LIB="${ROOT}/scripts/lib"
cd "$ROOT"
FAIL=0

pass() { echo "Gate $1: PASS — $2"; }
fail() { echo "Gate $1: FAIL — $2" >&2; FAIL=1; }

# SUB-RAW-REDACT: the raw command must mask secret-bearing keys at every depth.
if python3 - "$LIB" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import json
from subaru_core import _redact_raw, REDACTED
raw = {"session": {"accessToken": "abc"}, "authToken": "secret",
       "nested": [{"pin": "1234"}], "vehicle_status": {"ODOMETER": 1}}
out = _redact_raw(raw)
text = json.dumps(out)
assert out["session"] == REDACTED, out
assert out["authToken"] == REDACTED, out
assert out["nested"][0]["pin"] == REDACTED, out
assert out["vehicle_status"]["ODOMETER"] == 1, out
assert "abc" not in text and "secret" not in text and "1234" not in text, text
PY
then pass SUB-RAW-REDACT "raw payload redacts secrets"; else fail SUB-RAW-REDACT "redaction leaked secrets"; fi

# SUB-BRIDGE-MAPS: maps-link must not resolve to /status; vin reads route via /command.
if python3 - "$LIB" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from subaru_bridge_client import map_command_to_http
m, p, _ = map_command_to_http("maps-link", {})
assert (m, p) == ("GET", "/maps-link"), (m, p)
m, p, b = map_command_to_http("status", {"vin": "V1"})
assert (m, p) == ("POST", "/command") and b["args"]["vin"] == "V1", (m, p, b)
PY
then pass SUB-BRIDGE-MAPS "bridge maps-link + vin routing correct"; else fail SUB-BRIDGE-MAPS "bridge routing wrong"; fi

# SUB-SHIM-BIND: shim binds loopback by default, LAN only on opt-in.
if python3 - "$ROOT" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("shim", sys.argv[1] + "/scripts/talk-webhook-shim.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
assert mod.resolve_listen_host({}) == "127.0.0.1"
assert mod.resolve_listen_host({"TALK_SHIM_LAN": "1"}) == "0.0.0.0"
assert mod.resolve_listen_host({"TALK_SHIM_HOST": "10.0.0.5"}) == "10.0.0.5"
PY
then pass SUB-SHIM-BIND "shim loopback default + LAN opt-in"; else fail SUB-SHIM-BIND "shim bind default wrong"; fi

# SUB-UPDATE-THROTTLE: a recent update attempt is coalesced; force/old bypass.
if python3 - "$LIB" <<'PY'
import sys, json, tempfile, os
from datetime import datetime, timezone, timedelta
sys.path.insert(0, sys.argv[1])
from subaru_core import Settings, SubaruRunner
tmp = tempfile.mkdtemp()
os.environ["OPENCLAW_DIR"] = tmp
os.environ["SUBARU_UPDATE_MIN_INTERVAL_S"] = "600"
s = Settings(dry_run=False)
del os.environ["OPENCLAW_DIR"]; del os.environ["SUBARU_UPDATE_MIN_INTERVAL_S"]
r = SubaruRunner(s)
s.update_state.parent.mkdir(parents=True, exist_ok=True)
s.update_state.write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()}))
assert r._update_throttled() is True
assert r._update_throttled(force=True) is False
s.update_state.write_text(json.dumps({"timestamp": (datetime.now(timezone.utc)-timedelta(seconds=1200)).isoformat()}))
assert r._update_throttled() is False
PY
then pass SUB-UPDATE-THROTTLE "update throttle coalesces recent attempts"; else fail SUB-UPDATE-THROTTLE "throttle logic wrong"; fi

# SUB-ALERT-TRANSITION: a new condition posts once and dedups on repeat.
if python3 - "$LIB" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from subaru_conditions import condition_signature, should_post_conditions
sig = condition_signature([{"id": "H-DOOR", "status": "warn", "message": "boot OPEN"}])
post, msgs, _ = should_post_conditions([], sig)
assert post and msgs == ["boot OPEN"], (post, msgs)
post2, _, _ = should_post_conditions(sig, sig)
assert post2 is False
PY
then pass SUB-ALERT-TRANSITION "condition transition posts once"; else fail SUB-ALERT-TRANSITION "transition logic wrong"; fi

# SUB-SCHED-START-DRY: scheduled start dry-run blocks when actuation disabled.
out_off="$(SUBARU_ACTUATION_ENABLED=0 bash "${SCRIPT_DIR}/subaru-scheduled-start.sh" --dry-run 2>/dev/null || true)"
out_on="$(SUBARU_ACTUATION_ENABLED=1 bash "${SCRIPT_DIR}/subaru-scheduled-start.sh" --dry-run --preset Winter 2>/dev/null || true)"
if [[ "$out_off" == *"blocked=actuation_disabled"* && "$out_on" == *"start --preset Winter"* ]]; then
  pass SUB-SCHED-START-DRY "scheduled start dry-run gating correct"
else
  fail SUB-SCHED-START-DRY "off=[$out_off] on=[$out_on]"
fi

# SUB-TRIPLOG: weekly digest computes miles from a sample window.
if python3 - "$LIB" <<'PY'
import sys
from datetime import datetime, timezone, timedelta
sys.path.insert(0, sys.argv[1])
from subaru_trips import weekly_digest
now = datetime.now(timezone.utc)
s = [{"ts": (now-timedelta(days=5)).isoformat(), "odometer": 1000},
     {"ts": now.isoformat(), "odometer": 1142}]
assert weekly_digest(s, now=now) == "Driven last 7d: 142 mi"
PY
then pass SUB-TRIPLOG "trip weekly digest correct"; else fail SUB-TRIPLOG "trip digest wrong"; fi

# SUB-VIN-ARG: dispatch alias selects VIN; CLI accepts --vin in dry-run.
if python3 - "$LIB" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from subaru_dispatch_parse import parse_dispatch
out = parse_dispatch("@openclaw subaru outback status", "openclaw", {"outback": "VIN9"})
assert out == {"action": "status", "args": ["--vin", "VIN9"]}, out
PY
then
  if bash "${SCRIPT_DIR}/subaru-vehicle.sh" --dry-run --vin TESTVIN status >/dev/null 2>&1; then
    pass SUB-VIN-ARG "dispatch alias + CLI --vin accepted"
  else
    fail SUB-VIN-ARG "CLI --vin rejected"
  fi
else
  fail SUB-VIN-ARG "dispatch alias did not select vin"
fi

# SUB-GEOCODE: offline-safe — disabled returns None, fetcher path returns label.
if python3 - "$LIB" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from subaru_geocode import reverse_geocode
assert reverse_geocode(45.5, -122.6, enabled=False) is None
assert reverse_geocode(45.5, -122.6, enabled=True, fetcher=lambda a, b: "Beaverton, OR") == "Beaverton, OR"
assert reverse_geocode(None, None, enabled=True, fetcher=lambda a, b: "x") is None
PY
then pass SUB-GEOCODE "reverse geocode offline-safe"; else fail SUB-GEOCODE "geocode not offline-safe"; fi

echo ""
echo "=== subaru-feature-gates summary (hard_fail=$FAIL) ==="
exit "$FAIL"
