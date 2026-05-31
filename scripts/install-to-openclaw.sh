#!/usr/bin/env bash
# Symlink openclaw-subaru into ~/.openclaw (idempotent).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OPENCLAW_DIR="${OPENCLAW_DIR:-$HOME/.openclaw}"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

mkdir -p "${OPENCLAW_DIR}/scripts" "${OPENCLAW_DIR}/workspace/skills" "${OPENCLAW_DIR}/config" "${OPENCLAW_DIR}/workspace/references"

link_one() {
  local src="$1" dst="$2"
  if [[ -L "$dst" ]]; then
    cur=$(readlink -f "$dst" 2>/dev/null || readlink "$dst")
    [[ "$cur" == "$src" ]] && return 0
    rm -f "$dst"
  elif [[ -e "$dst" ]]; then
    if [[ "$FORCE" -eq 1 ]]; then
      rm -rf "$dst"
    else
      echo "install: skip existing $dst (use --force to replace with symlink)" >&2
      return 0
    fi
  fi
  ln -sf "$src" "$dst"
}

sync_skill() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [[ -L "$dst" ]]; then
    rm -f "$dst"
  elif [[ -d "$dst" && "$FORCE" -eq 0 ]]; then
    echo "install: skip existing skill dir $dst (use --force to refresh copy)" >&2
    return 0
  fi
  rm -rf "$dst"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a "${src}/" "${dst}/"
  else
    cp -a "${src}" "${dst}"
  fi
}

for f in "${ROOT}"/scripts/*.sh; do
  base=$(basename "$f")
  case "$base" in
    install-to-openclaw.sh|scrub-for-publish.sh|publish-gates.sh) continue ;;
  esac
  link_one "$f" "${OPENCLAW_DIR}/scripts/$base"
done

for f in "${ROOT}"/scripts/*.py; do
  [[ -f "$f" ]] || continue
  base=$(basename "$f")
  link_one "$f" "${OPENCLAW_DIR}/scripts/$base"
done

if [[ -d "${ROOT}/scripts/lib" ]]; then
  mkdir -p "${OPENCLAW_DIR}/scripts/lib"
  for f in "${ROOT}"/scripts/lib/*.py; do
    [[ -f "$f" ]] || continue
    base=$(basename "$f")
    link_one "$f" "${OPENCLAW_DIR}/scripts/lib/$base"
  done
fi

if [[ -f "${ROOT}/scripts/talk-webhook-shim.py" ]]; then
  cp "${ROOT}/scripts/talk-webhook-shim.py" "${OPENCLAW_DIR}/talk-webhook-shim.py"
  echo "install: copied talk-webhook-shim.py → ${OPENCLAW_DIR}/talk-webhook-shim.py"
fi

sync_skill "${ROOT}/skills/subaru-vehicle" "${OPENCLAW_DIR}/workspace/skills/subaru-vehicle"

if [[ -f "${OPENCLAW_DIR}/.env" ]]; then
  # shellcheck source=/dev/null
  source "${OPENCLAW_DIR}/.env"
  if [[ -n "${OPENCLAW_AGENT_MENTION:-}" && "${OPENCLAW_AGENT_MENTION}" != "@openclaw" ]]; then
    find "${OPENCLAW_DIR}/workspace/skills/subaru-vehicle" -name 'SKILL.md' -print0 2>/dev/null \
      | while IFS= read -r -d '' f; do
          sed -i 's/@openclaw/'"${OPENCLAW_AGENT_MENTION}"'/g' "$f"
        done
  fi
fi

if [[ ! -f "${OPENCLAW_DIR}/config/subaru-vehicle.json" ]]; then
  cp "${ROOT}/config/subaru-vehicle.example.json" "${OPENCLAW_DIR}/config/subaru-vehicle.json"
  echo "install: copied subaru-vehicle.example.json → ~/.openclaw/config/subaru-vehicle.json (edit VIN + nickname)"
fi

for ref in cron-shell-direct.yaml; do
  src="${ROOT}/config/references/${ref}"
  dst="${OPENCLAW_DIR}/workspace/references/${ref}"
  if [[ -f "$src" && ! -f "$dst" ]]; then
    cp "$src" "$dst"
    echo "install: copied workspace/references/${ref} (edit locally; not overwritten on re-install)"
  fi
done

export OPENCLAW_SUBARU_ROOT="$ROOT"

_i3_fail=0
_p="${OPENCLAW_DIR}/workspace/skills/subaru-vehicle"
if [[ ! -d "$_p" ]]; then
  echo "FAIL I3: missing skill dir $_p" >&2
  _i3_fail=1
else
  _real=$(readlink -f "$_p" 2>/dev/null || echo "$_p")
  case "$_real" in
    "${OPENCLAW_DIR}/workspace/skills/"*) echo "PASS I3: subaru-vehicle under workspace" ;;
    *) echo "FAIL I3: subaru-vehicle resolves outside workspace ($_real)" >&2; _i3_fail=1 ;;
  esac
fi
[[ "$_i3_fail" -eq 0 ]] || exit 1

echo "Gate I1: install ok — OPENCLAW_SUBARU_ROOT=$ROOT"
echo "Re-run safe: symlinks updated idempotently (I2)"
echo "Note: skill is copied (not symlinked). Re-run --force after skill updates."
echo "Talk alerts: set SUBARU_ALERT_TALK_ROOM or install openclaw-skylight for talk-post.sh"
