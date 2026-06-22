#!/usr/bin/env bash
# Shared helpers for aws/*.sh scripts. Source this from each script:
#   source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"
# Never run directly.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AWS_DIR="$ROOT_DIR/aws"
# INFRA_DIR is consumed by the scripts that source this lib (create/redeploy/destroy).
# shellcheck disable=SC2034
INFRA_DIR="$ROOT_DIR/infra"

# Load environment: aws/.env if present, else aws/env.example. Every
# assignment is exported (set -a) so child processes (aws, cdk) inherit it.
if [ -f "$AWS_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$AWS_DIR/.env"
  set +a
elif [ -f "$AWS_DIR/env.example" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$AWS_DIR/env.example"
  set +a
fi

# CloudFront's ACM cert must live in us-east-1, so the whole stack is pinned there.
export AWS_REGION="${AWS_REGION:-us-east-1}"
export CDK_DEFAULT_REGION="$AWS_REGION"
if command -v aws >/dev/null 2>&1; then
  CDK_DEFAULT_ACCOUNT="${CDK_DEFAULT_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)}"
  export CDK_DEFAULT_ACCOUNT
fi

# Verbatim CloudFormation stack name from infra/scotus_stack.py.
STACK_NAME="${STACK_NAME:-ScotusStack}"

color() {
  local c="$1"; shift
  printf "\033[%sm%s\033[0m\n" "$c" "$*"
}
info()  { color "36" "ℹ $*"; }
ok()    { color "32" "✓ $*"; }
warn()  { color "33" "⚠ $*"; }
err()   { color "31" "✗ $*" 1>&2; }

# stack_output <OutputKey> — echoes the CloudFormation output value (empty if absent).
stack_output() {
  local key="$1"
  aws cloudformation describe-stacks \
    --region "$AWS_REGION" \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$key'].OutputValue" \
    --output text 2>/dev/null
}

require_cmd() {
  for c in "$@"; do
    if ! command -v "$c" >/dev/null 2>&1; then
      err "Missing required command: $c"
      exit 1
    fi
  done
}

# confirm <prompt> [expected] — abort unless the user types <expected> (default "y").
confirm() {
  local prompt="$1"
  local expected="${2:-y}"
  local ans
  read -r -p "$prompt " ans
  if [ "$ans" != "$expected" ]; then
    err "Aborted."
    exit 1
  fi
}
