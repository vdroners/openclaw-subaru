#!/usr/bin/env bash
# Interactive MySubaru auth bootstrap (PIN + optional 2FA device registration).
# Usage: subaru-auth-bootstrap.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

echo "Subaru auth bootstrap — uses subarulink interactive session."
echo "Ensure SUBARU_USERNAME, SUBARU_PASSWORD_FILE, SUBARU_PIN_FILE are set."
echo ""

if [[ ! -x "${SUBARU_VENV}/bin/pip" ]]; then
  python3 -m venv "${SUBARU_VENV}"
  "${SUBARU_VENV}/bin/pip" install -r "$(cd "${SCRIPT_DIR}/.." && pwd)/requirements.txt"
fi

export SUBARU_ENABLED=1
echo "Running: subaru auth check (live)"
bash "${SCRIPT_DIR}/subaru-vehicle.sh" auth check || true
echo ""
echo "If auth check failed, run subarulink interactively once:"
echo "  ${SUBARU_VENV}/bin/subarulink -i -c ${SUBARU_CONFIG_FILE}"
echo "Then re-run: bash ${SCRIPT_DIR}/subaru-gates.sh --check --live"
