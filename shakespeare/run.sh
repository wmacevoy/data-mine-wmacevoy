#!/usr/bin/env bash
cd -- "$(dirname -- "${BASH_SOURCE[0]}")" || exit 1

case "$1" in
  api)
    shift
    ./python.sh -m uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload "$@"
    ;;
  all)
    # Start services and open dashboard; then start JupyterLab
    docker compose up -d || exit 1
    cleanup() { echo "\n>> Shutting down services..."; docker compose down ; }
    trap cleanup INT TERM EXIT
    if command -v open >/dev/null 2>&1; then open http://localhost:8080; fi
    ./jupyter.sh lab
    ;;
  down)
    docker compose down
    ;;
  *)
    ./jupyter.sh lab "$@"
    ;;
esac