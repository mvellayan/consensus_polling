#!/usr/bin/env bash
# Shared helpers for admin/*.sh (data + judge lifecycle scripts).
# Sourced, never run directly.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Load OPENAI_API_KEY from the repo-root .env (used by the judge python scripts
# and the OpenAI REST cleanup). Exported for child processes.
if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

# DynamoDB tables / region for the data tools. The physical table names are
# fixed in infra/scotus_stack.py (TABLE_PREFIX="scotus").
AWS_REGION="${AWS_REGION:-us-east-1}"
QUERIES_TABLE="${QUERIES_TABLE:-scotusQueries}"
RESPONSES_TABLE="${RESPONSES_TABLE:-scotusResponses}"

color() {
  local c="$1"; shift
  printf "\033[%sm%s\033[0m\n" "$c" "$*"
}
info()  { color "36" "ℹ $*"; }
ok()    { color "32" "✓ $*"; }
warn()  { color "33" "⚠ $*"; }
err()   { color "31" "✗ $*" 1>&2; }

require_cmd() {
  for c in "$@"; do
    if ! command -v "$c" >/dev/null 2>&1; then
      err "Missing required command: $c"
      exit 1
    fi
  done
}
