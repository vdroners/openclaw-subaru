#!/usr/bin/env bash
# Validate subaru-vehicle.json against schema (python3 + json).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET="${1:-${ROOT}/config/subaru-vehicle.example.json}"
SCHEMA="${ROOT}/config/subaru-vehicle.schema.json"

python3 - "$TARGET" "$SCHEMA" <<'PY'
import json, re, sys
from pathlib import Path

path = Path(sys.argv[1])
schema_path = Path(sys.argv[2])
if not path.is_file():
    print(f"Gate SUB-X: FAIL — missing {path}", file=sys.stderr)
    sys.exit(1)
data = json.loads(path.read_text())
schema = json.loads(schema_path.read_text())
required = schema.get("required", [])
missing = [k for k in required if k not in data]
if missing:
    print(f"Gate SUB-X: FAIL — missing keys {missing}", file=sys.stderr)
    sys.exit(1)
vin = str(data.get("vin", ""))
if not re.match(r"^[A-HJ-NPR-Z0-9]{11,17}$", vin):
    print(f"Gate SUB-X: FAIL — invalid VIN format", file=sys.stderr)
    sys.exit(1)
if "alert_thresholds" in data:
    at = data["alert_thresholds"]
    if at.get("fuel_percent_fail", 0) > at.get("fuel_percent_warn", 100):
        print("Gate SUB-X: FAIL — fuel_percent_fail > fuel_percent_warn", file=sys.stderr)
        sys.exit(1)
print(f"Gate SUB-X: PASS — {path.name} valid")
PY
