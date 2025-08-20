#!/usr/bin/env bash
# px.sh — ensure env is ready, then run px.py in it (passes args through)

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# -------------------- Wrapper Args --------------------
SHOW_HELP=false
DO_RESET=false
DO_RESTART=false

PASSTHRU_ARGS=()
SEEN_DASH_DASH=false

for arg in "${@:-}"; do
  if $SEEN_DASH_DASH; then
    PASSTHRU_ARGS+=("$arg")
    continue
  fi
  case "${arg:-}" in
    --help|-h)
      SHOW_HELP=true ;;
    --reset)
      DO_RESET=true ;;
    --restart)
      DO_RESTART=true ;;
    --)
      SEEN_DASH_DASH=true ;;
    *)
      PASSTHRU_ARGS+=("$arg") ;;
  esac
done

if $SHOW_HELP; then
  cat <<'EOF'
Usage: ./px.sh [--help] [--reset] [--restart] [--] <px.py args>

Wrapper options (handled by px.sh):
  --help      Show this help and exit
  --reset     Clean data load only:
              - Clears cached data (./data/)
              - Clears debug snapshots (./debug/)
  --restart   Rebuild environment from scratch (also implies setup):
              - Removes ./.venv and recreates it via setup.sh

Notes:
  - Arguments after "--" are passed directly to px.py.
  - To see px.py's own CLI help, run:  ./px.sh -- --help
  - This wrapper ensures the conda/mamba env at ./.venv exists and then runs:
      python px.py <args>
EOF
  exit 0
fi

if $DO_RESTART && [[ -d .venv ]]; then
  echo ">> Removing existing env: $SCRIPT_DIR/.venv"
  rm -rf .venv
fi

if $DO_RESET; then
  echo ">> Resetting cached data and debug snapshots"
  mkdir -p data debug
  rm -f data/*.parquet || true
  rm -rf debug/* || true
fi

if [[ ! -d .venv ]]; then
  ./setup.sh
fi

# pick mamba or conda
if command -v mamba >/dev/null 2>&1; then
  CONDA_BIN="mamba"
elif command -v conda >/dev/null 2>&1; then
  CONDA_BIN="conda"
else
  echo "ERROR: neither 'mamba' nor 'conda' found in PATH." >&2
  exit 1
fi

"$CONDA_BIN" run -p "$SCRIPT_DIR/.venv" python px.py "${PASSTHRU_ARGS[@]:-}"


