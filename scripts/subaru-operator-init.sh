#!/usr/bin/env bash
# Interactive operator bootstrap checklist (local secrets only — never commit).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"

echo "Subaru operator bootstrap — writes under ${OPENCLAW_DIR} only."
echo ""

mkdir -p "${OPENCLAW_DIR}/.env.d" "${OPENCLAW_DIR}/config" "${OPENCLAW_DIR}/state"

if [[ ! -f "${OPENCLAW_DIR}/.env" ]]; then
  cat >"${OPENCLAW_DIR}/.env" <<'EOF'
SUBARU_ENABLED=1
SUBARU_USERNAME=
SUBARU_PASSWORD_FILE=~/.openclaw/.env.d/subaru-password
SUBARU_PIN_FILE=~/.openclaw/.env.d/subaru-pin
SUBARU_VIN=
SUBARU_COUNTRY=USA
SUBARU_DEVICE_NAME=openclaw-homelab
SUBARU_VEHICLE_JSON=~/.openclaw/config/subaru-vehicle.json
SUBARU_ACTUATION_ENABLED=0
SUBARU_VENV=~/.openclaw/venv-subaru
EOF
  echo "Created ${OPENCLAW_DIR}/.env template — edit SUBARU_USERNAME and SUBARU_VIN"
fi

if [[ ! -f "${OPENCLAW_DIR}/config/subaru-vehicle.json" ]]; then
  cp "${ROOT}/config/subaru-vehicle.example.json" "${OPENCLAW_DIR}/config/subaru-vehicle.json"
  echo "Copied vehicle JSON example — set vin/nickname/remote_start_preset"
fi

for f in subaru-password subaru-pin; do
  path="${OPENCLAW_DIR}/.env.d/${f}"
  if [[ ! -f "$path" ]]; then
    touch "$path"
    chmod 600 "$path"
    echo "Created ${path} (mode 600) — paste secret manually"
  fi
done

echo ""
echo "Next steps:"
echo "  1. Edit ${OPENCLAW_DIR}/.env (SUBARU_USERNAME, SUBARU_VIN)"
echo "  2. Write password to ${OPENCLAW_DIR}/.env.d/subaru-password"
echo "  3. Write PIN to ${OPENCLAW_DIR}/.env.d/subaru-pin"
echo "  4. python3 -m venv ${OPENCLAW_DIR}/venv-subaru && pip install -r ${ROOT}/requirements.txt"
echo "  5. bash ${SCRIPT_DIR}/install-to-openclaw.sh --force"
echo "  6. bash ${SCRIPT_DIR}/subaru-auth-bootstrap.sh"
echo "  7. make -C ${ROOT} gates"
echo "  8. bash ${SCRIPT_DIR}/subaru-gates.sh --check --live"
