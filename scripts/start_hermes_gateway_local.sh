#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

PROJECT_ROOT="/Users/apple/Downloads/User/New-Radar"
HERMES_BIN="/Users/apple/Downloads/User/New-Radar/hermes-agent/venv/bin/hermes"

cd "$PROJECT_ROOT"
docker compose up -d db

export HERMES_HOME="$HOME/.hermes"
export DB_HOST="127.0.0.1"
export DB_PORT="5444"
export DB_USER="radar"
export DB_PASSWORD="radar"
export DB_NAME="radar"
export DB_DIALECT="postgresql"

exec "$HERMES_BIN" gateway run
