#!/usr/bin/env bash
# Tear down ScotusStack. Requires typing DESTROY to proceed.
#
# NOTE: the two DynamoDB tables (scotusQueries, scotusResponses) use
# RemovalPolicy.RETAIN — they SURVIVE this destroy and must be deleted by hand
# if you truly want them gone.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

require_cmd npx

warn "This will destroy stack: $STACK_NAME (region $AWS_REGION)."
warn "RETAINed DynamoDB tables (scotusQueries, scotusResponses) will SURVIVE and"
warn "must be deleted manually if you want them removed."
confirm "Type DESTROY to continue:" "DESTROY"

info "Destroying $STACK_NAME ..."
( cd "$INFRA_DIR" && npx aws-cdk destroy --force )

ok "Stack destroyed. Note: RETAINed tables remain."
