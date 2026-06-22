#!/usr/bin/env bash
# Re-deploy code changes without re-bootstrapping. Re-uploads the Lambda asset
# (the Quart app zip) and applies any infra diff.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

require_cmd npx

info "Re-deploying $STACK_NAME (re-uploads the Lambda asset) ..."
( cd "$INFRA_DIR" && npx aws-cdk deploy --require-approval never )

ok "Redeploy complete."
echo "  AppUrl:      $(stack_output AppUrl)"
echo "  FunctionUrl: $(stack_output FunctionUrl)"
