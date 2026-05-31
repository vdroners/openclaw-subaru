#!/usr/bin/env bash
# Format subaru-vehicle JSON (stdin) for Talk posting.
# Usage: subaru-vehicle.sh status | subaru-format-talk-reply.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"
exec "$SUBARU_PYTHON" "${SCRIPT_DIR}/lib/subaru_format_talk_reply.py"
