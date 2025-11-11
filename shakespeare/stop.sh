#!/usr/bin/env bash
# stop.sh — stop local services (docker compose down)

cd -- "$(dirname -- "${BASH_SOURCE[0]}")" || exit 1

DO_VOLUMES=false
for arg in "$@"; do
  case "$arg" in
    --volumes|-v) DO_VOLUMES=true ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not in PATH" 1>&2
  exit 1
fi

if $DO_VOLUMES; then
  echo ">> docker compose down -v"
  docker compose down -v
else
  echo ">> docker compose down"
  docker compose down
fi


