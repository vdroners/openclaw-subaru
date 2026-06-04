#!/usr/bin/env bash
# Test Talk fast-path phrase parsing (no network).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-agent-env.sh" 2>/dev/null || true
MENTION="${OPENCLAW_AGENT_MENTION:-@openclaw}"
FAIL=0

phrases=(
  "${MENTION} subaru status"
  "${MENTION} subaru"
  "${MENTION} subaru summary"
  "${MENTION} subaru health"
  "${MENTION} subaru health-report"
  "${MENTION} subaru locate"
  "${MENTION} subaru maps"
  "${MENTION} subaru maps-link"
  "${MENTION} subaru condition"
  "${MENTION} subaru capabilities"
  "${MENTION} subaru fetch"
  "${MENTION} subaru lock"
  "${MENTION} subaru unlock"
  "${MENTION} subaru unlock driver"
  "${MENTION} subaru start Winter"
  "${MENTION} subaru stop"
  "${MENTION} subaru horn"
  "${MENTION} subaru lights"
)

for msg in "${phrases[@]}"; do
  if ! bash "${SCRIPT_DIR}/subaru-dispatch.sh" "$msg" >/tmp/subaru-dispatch-test.json 2>/dev/null; then
    echo "SUB-DISPATCH FAIL: $msg" >&2
    FAIL=1
    continue
  fi
  if ! python3 -c "import json; json.load(open('/tmp/subaru-dispatch-test.json'))"; then
    echo "SUB-DISPATCH FAIL: invalid JSON for $msg" >&2
    FAIL=1
  fi
done

if bash "${SCRIPT_DIR}/subaru-dispatch.sh" "${MENTION} subaru health-report" >/tmp/subaru-dispatch-hr.json 2>/dev/null; then
  action="$(python3 -c "import json; print(json.load(open('/tmp/subaru-dispatch-hr.json'))['action'])")"
  if [[ "$action" != "health-report" ]]; then
    echo "SUB-DISPATCH FAIL: health-report mapped to $action" >&2
    FAIL=1
  fi
fi

if bash "${SCRIPT_DIR}/subaru-dispatch.sh" "hello world" >/dev/null 2>&1; then
  echo "SUB-DISPATCH FAIL: non-subaru should exit 1" >&2
  FAIL=1
fi

# Talk fast-path renders bare "subaru status" via the richer summary deck.
if SUBARU_TALK_FASTPATH=1 bash "${SCRIPT_DIR}/subaru-dispatch-exec.sh" --dry-run "${MENTION} subaru status" >/tmp/subaru-fastpath-map.out 2>/dev/null; then
  if ! grep -q 'action=summary' /tmp/subaru-fastpath-map.out; then
    echo "SUB-DISPATCH FAIL: fast-path status should map to summary" >&2
    FAIL=1
  fi
else
  echo "SUB-DISPATCH FAIL: fast-path dispatch-exec dry-run failed" >&2
  FAIL=1
fi

if [[ "$FAIL" -eq 0 ]]; then
  echo "SUB-DISPATCH_TEST_OK phrases=${#phrases[@]}"
fi
exit "$FAIL"
