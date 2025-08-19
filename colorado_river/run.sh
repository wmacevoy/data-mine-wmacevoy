#!/usr/bin/env bash
# run.sh — ensure env is ready, then run Streamlit in it

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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
