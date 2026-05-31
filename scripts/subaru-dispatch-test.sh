#!/usr/bin/env bash
# Test Talk fast-path phrase parsing (no network).
# Usage: subaru-dispatch-test.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAIL=0

phrases=(
  '@openclaw subaru status'
  '@openclaw subaru summary'
  '@openclaw subaru health'
  '@openclaw subaru locate'
  '@openclaw subaru maps'
  '@openclaw subaru condition'
  '@openclaw subaru capabilities'
  '@openclaw subaru fetch'
  '@openclaw subaru lock'
  '@openclaw subaru unlock'
  '@openclaw subaru unlock driver'
  '@openclaw subaru start Winter'
  '@openclaw subaru stop'
  '@openclaw subaru horn'
  '@openclaw subaru lights'
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

if [[ "$FAIL" -eq 0 ]]; then
  echo "SUB-DISPATCH_TEST_OK phrases=${#phrases[@]}"
fi
exit "$FAIL"
