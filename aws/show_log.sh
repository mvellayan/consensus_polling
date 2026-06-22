#!/usr/bin/env bash
# Tail the Lambda's CloudWatch logs.
#   aws/show_log.sh [--since <duration>]
# Default window is 10m. Examples: --since 1h, --since 30m.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

require_cmd aws

since="10m"
if [ "${1:-}" = "--since" ]; then
  if [ -z "${2:-}" ]; then
    err "--since requires a value (e.g. 1h, 30m)"
    exit 1
  fi
  since="$2"
fi

# Function name is fixed in infra/scotus_stack.py (function_name="scotus-app").
fn_name="scotus-app"
log_group="/aws/lambda/$fn_name"

info "Tailing $log_group (since $since) — Ctrl-C to stop ..."
aws logs tail "$log_group" \
  --region "$AWS_REGION" \
  --since "$since" \
  --follow
