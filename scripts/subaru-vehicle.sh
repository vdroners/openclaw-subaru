#!/usr/bin/env bash
# Bash facade for MySubaru commands (OpenClaw exec target).
# Usage: subaru-vehicle.sh [--dry-run] <command> [args...]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load-subaru-env.sh"

DRY_RUN=0
BRIDGE=0
VIN_ARG=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --bridge) BRIDGE=1; shift ;;
    --vin) VIN_ARG=( --vin "$2" ); shift 2 ;;
    *) break ;;
  esac
done

if [[ $# -lt 1 ]]; then
  echo "usage: subaru-vehicle.sh [--dry-run] [--vin VIN] <command> [args...]" >&2
  exit 2
fi

CMD=( "$SUBARU_PYTHON" "${SCRIPT_DIR}/subaru_cli.py" )
[[ "$DRY_RUN" -eq 1 ]] && CMD+=( --dry-run )
if [[ ${#VIN_ARG[@]} -gt 0 ]]; then
  CMD+=( "${VIN_ARG[@]}" )
fi
if [[ -n "${SUBARU_BRIDGE_URL:-}" && "$DRY_RUN" -eq 0 ]] || [[ "$BRIDGE" -eq 1 && "$DRY_RUN" -eq 0 ]]; then
  CMD+=( --bridge )
  export SUBARU_BRIDGE_URL="${SUBARU_BRIDGE_URL:-http://127.0.0.1:8790}"
fi

# Map shell-style multi-word commands to CLI subcommands
case "$1" in
  health-report) CMD+=( health-report ); shift ;;
  maps-link) CMD+=( maps-link ); shift ;;
  remote_start) CMD+=( remote_start ); shift ;;
  remote_stop) CMD+=( remote_stop ); shift ;;
  auth)
    shift
    [[ "${1:-}" == "connect" || "${1:-}" == "check" ]] || { echo "auth requires connect|check" >&2; exit 2; }
    CMD+=( auth "$1" ); shift
    ;;
  pin)
    shift
    [[ "${1:-}" == "test" ]] || { echo "pin requires test" >&2; exit 2; }
    CMD+=( pin test ); shift
    ;;
  presets)
    shift
    sub="${1:-}"; shift || true
    case "$sub" in
      list) CMD+=( presets list ) ;;
      show) CMD+=( presets show ) ;;
      get) CMD+=( presets get "${1:-}" ); shift || true ;;
      default) CMD+=( presets default "${1:-}" ); shift || true ;;
      delete) CMD+=( presets delete "${1:-}" ); shift || true ;;
      add)
        file=""
        while [[ $# -gt 0 ]]; do
          case "$1" in
            --file) file="$2"; shift 2 ;;
            *) shift ;;
          esac
        done
        CMD+=( presets add --file "$file" )
        ;;
      *) echo "presets requires list|show|get|default|delete|add" >&2; exit 2 ;;
    esac
    ;;
  vehicles)
    shift
    sub="${1:-}"; shift || true
    case "$sub" in
      list) CMD+=( vehicles list ) ;;
      select) CMD+=( vehicles select "${1:-}" ); shift || true ;;
      *) echo "vehicles requires list|select" >&2; exit 2 ;;
    esac
    ;;
  config)
    shift
    [[ "${1:-}" == "set" ]] || { echo "config requires set KEY VALUE" >&2; exit 2; }
    shift
    key="${1:-}"; val="${2:-}"
    CMD+=( config set "$key" "$val" ); shift 2 || true
    ;;
  unlock)
    CMD+=( unlock )
    shift
    door="all"
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --door) door="$2"; shift 2 ;;
        driver|drivers|tailgate|all) door="$1"; shift ;;
        *) shift ;;
      esac
    done
    CMD+=( --door "$door" )
    ;;
  start)
    CMD+=( start )
    shift
    preset=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --preset) preset="$2"; shift 2 ;;
        *) preset="$1"; shift ;;
      esac
    done
    [[ -n "$preset" ]] && CMD+=( --preset "$preset" )
    ;;
  horn|lights)
    base="$1"
    CMD+=( "$base" )
    shift
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --stop) CMD+=( --stop ); shift ;;
        *) shift ;;
      esac
    done
    ;;
  locate)
    CMD+=( locate )
    shift
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --force) CMD+=( --force ); shift ;;
        *) shift ;;
      esac
    done
    ;;
  *)
    CMD+=( "$1" ); shift
    CMD+=( "$@" )
    ;;
esac

if [[ -n "${SUBARU_BRIDGE_URL:-}" && "$DRY_RUN" -eq 0 ]] || [[ "$BRIDGE" -eq 1 && "$DRY_RUN" -eq 0 ]]; then
  export SUBARU_BRIDGE_URL="${SUBARU_BRIDGE_URL:-http://127.0.0.1:8790}"
fi

out="$(mktemp)"
trap 'rm -f "$out"' EXIT
if ! "${CMD[@]}" >"$out" 2>/dev/null; then
  cat "$out" >&2 || true
  echo "SUBARU_ERR command failed" >&2
  exit 1
fi
cat "$out"
if python3 - "$out" <<'PY' >&2
import json, sys
payload = json.load(open(sys.argv[1]))
print("SUBARU_OK" if payload.get("ok") else "SUBARU_ERR")
sys.exit(0 if payload.get("ok") else 1)
PY
then
  :
else
  exit 1
fi
