#!/usr/bin/env bash
# Optional one-liner for family morning digest (fuel + health score).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

if [[ "${SUBARU_ENABLED:-0}" != "1" || "${SUBARU_MORNING_BRIEF:-0}" != "1" ]]; then
  exit 0
fi

summary="$(bash "${SCRIPT_DIR}/subaru-vehicle.sh" summary 2>/dev/null || echo '{}')"
line="$(python3 -c "
import json, sys
p = json.loads(sys.argv[1])
text = p.get('data', {}).get('summary_text', '')
print('Subaru: ' + (text.split(chr(10))[0] if text else 'no data'))
" "$summary" 2>/dev/null || echo "Subaru: (unavailable)")"
echo "$line"
