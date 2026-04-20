#!/usr/bin/env bash
# Thin wrapper around `docker compose` for the Chronos stack.
#
# Examples:
#   ./up.sh up --build
#   ./up.sh down -v
#   COMPOSE_FILE=compose.prod.yaml ENV_FILE=.env.prod ./up.sh up -d

set -euo pipefail

cd "$(dirname "$0")"

: "${COMPOSE_FILE:=compose.dev.yaml}"
: "${ENV_FILE:=.env.dev}"

exec docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
