#!/usr/bin/env bash
cd -- "$(dirname -- "${BASH_SOURCE[0]}")" || exit 1

case "$1" in
  api)
    shift
    ./python.sh -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload "$@"
    ;;
  *)
    ./jupyter.sh lab "$@"
    ;;
esac