#!/usr/bin/env bash
source "$(dirname -- "${BASH_SOURCE[0]}")"/context.sh
mkdir -p "$(conda_venv)/share/jupyter/runtime"
export JUPYTER_PREFER_ENV_PATH=1
export JUPYTER_PATH="$(conda_venv)/share/jupyter"
export JUPYTER_RUNTIME_DIR="$(conda_venv)/share/jupyter/runtime"
export PYTHONPATH="$(context_dir):${PYTHONPATH:-}"
if ! jupyter_exe "$@"
then
  echo "ERROR: jupyter_exe $@ failed" 1>&2
  exit 1
fi
