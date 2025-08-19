#!/usr/bin/env bash
# setup.sh — create/update a local .venv (mamba/conda) and install deps

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PY_VERSION="${PY_VERSION:-3.11}"
ENV_PREFIX="$SCRIPT_DIR/.venv"

# Pick mamba/conda
if command -v mamba >/dev/null 2>&1; then
  CONDA_BIN="mamba"
elif command -v conda >/dev/null 2>&1; then
  CONDA_BIN="conda"
else
  echo "ERROR: neither 'mamba' nor 'conda' found in PATH."
  exit 1
fi

# Create env if missing
if [[ ! -d "$ENV_PREFIX" ]]; then
  echo ">> Creating env at $ENV_PREFIX (python=$PY_VERSION)"
  "$CONDA_BIN" create -y -p "$ENV_PREFIX" "python=$PY_VERSION"
else
  echo ">> Env already exists at $ENV_PREFIX"
fi

# Install requirements using conda run
if [[ -f "requirements.txt" ]]; then
  echo ">> Installing requirements into $ENV_PREFIX"
  "$CONDA_BIN" run -p "$ENV_PREFIX" python -m pip install --upgrade pip
  "$CONDA_BIN" run -p "$ENV_PREFIX" python -m pip install -r requirements.txt
else
  echo "WARN: requirements.txt not found"
fi

echo ">> Setup complete."
echo "To use this env:"
echo "   $CONDA_BIN run -p $ENV_PREFIX streamlit run app.py"
echo "or, if you prefer activation:"
echo "   source activate $ENV_PREFIX   # (requires conda init)"
