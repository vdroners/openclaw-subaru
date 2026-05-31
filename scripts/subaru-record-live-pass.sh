#!/usr/bin/env bash
# Record manual Tier 3 actuation gate passes (interactive checklist).
# Writes ~/.openclaw/state/subaru-gates-live-pass.json
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

STATE="${OPENCLAW_DIR}/state/subaru-gates-live-pass.json"
mkdir -p "$(dirname "$STATE")"

gates=(
  "SUB-LIVE-LOCK:Remote lock confirmed"
  "SUB-LIVE-UNLOCK:Remote unlock + re-lock confirmed"
  "SUB-LIVE-UNLOCK-DRIVER:Driver door unlock confirmed"
  "SUB-LIVE-START:Remote start with default preset confirmed"
  "SUB-LIVE-STOP:Remote stop confirmed"
  "SUB-LIVE-HORN:Horn + horn stop confirmed"
  "SUB-LIVE-LIGHTS:Lights + lights stop confirmed"
)

tmp="$(mktemp)"
passed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "Subaru Tier 3 actuation checklist — answer y/n for each gate (safe parked context only)."
echo ""

for entry in "${gates[@]}"; do
  id="${entry%%:*}"
  desc="${entry#*:}"
  read -r -p "$id — $desc [y/N]: " ans
  if [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]]; then
    echo "${id}=true" >>"$tmp"
    echo "  recorded PASS"
  else
    echo "${id}=false" >>"$tmp"
    echo "  recorded SKIP/FAIL"
  fi
done

python3 - "$STATE" "$passed_at" "$tmp" <<'PY'
import json, sys
from pathlib import Path
state_path, passed_at, listing = sys.argv[1], sys.argv[2], Path(sys.argv[3])
gates = {}
for line in listing.read_text(encoding="utf-8").splitlines():
    if "=" not in line:
        continue
    k, v = line.split("=", 1)
    gates[k] = v.strip() == "true"
payload = {
    "passed_at": passed_at,
    "gates": gates,
    "note": "Operator-confirmed Tier 3 actuation gates",
}
Path(state_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {state_path}")
PY
rm -f "$tmp"

echo ""
echo "Next: set SUBARU_ACTUATION_ENABLED=1 in ~/.openclaw/.env after reviewing ${STATE}"
