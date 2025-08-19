#!/usr/bin/env bash
# run.sh — ensure env is ready, then run Streamlit in it

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# -------------------- Args --------------------
SHOW_HELP=false
DO_DEBUG=false
DO_RESET=false
DO_RESTART=false

for arg in "${@:-}"; do
  case "${arg:-}" in
    --help|-h)
      SHOW_HELP=true ;;
    --debug)
      DO_DEBUG=true
      DO_RESET=true ;;
    --reset)
      DO_RESET=true ;;
    --restart)
      DO_RESTART=true ;;
    *) ;;
  esac
done

if $SHOW_HELP; then
  cat <<'EOF'
Usage: ./run.sh [--help] [--debug] [--reset] [--restart]

Options:
  --help      Show this help and exit
  --debug     Enable extra debugging (implies --reset):
              - Clears cached data (./data/)
              - Clears debug snapshots (./debug/)
              - Exports STREAMLIT_DEBUG_SNAPSHOTS=1 for the app
  --reset     Clean data load only:
              - Clears cached data (./data/)
              - Clears debug snapshots (./debug/)
  --restart   Rebuild environment from scratch (also implies setup):
              - Removes ./.venv and recreates it via setup.sh

Behavior:
  - The script auto-creates .streamlit/config.toml to suppress first-run prompts
  - Streamlit runs headless using python -m streamlit
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

# Ensure a local Streamlit config to suppress first-run onboarding prompt
mkdir -p .streamlit
if [[ ! -f .streamlit/config.toml ]]; then
  cat > .streamlit/config.toml <<'EOF'
[browser]
gatherUsageStats = false

[server]
headless = true
EOF
fi

# Also set env vars explicitly for non-interactive runs
export STREAMLIT_BROWSER_GATHERUSAGESTATS=false
export STREAMLIT_SERVER_HEADLESS=true
if $DO_DEBUG; then
  export STREAMLIT_DEBUG_SNAPSHOTS=1
fi

# Step 2: pick mamba or conda
if command -v mamba >/dev/null 2>&1; then
  CONDA_BIN="mamba"
elif command -v conda >/dev/null 2>&1; then
  CONDA_BIN="conda"
else
  echo "ERROR: neither 'mamba' nor 'conda' found in PATH." >&2
  exit 1
fi

# Step 3: run streamlit inside the .venv env via python -m to avoid stale shebangs
"$CONDA_BIN" run -p "$SCRIPT_DIR/.venv" python -m streamlit run app.py
