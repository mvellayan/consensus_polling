#!/usr/bin/env bash
# Dump recent rows from the Queries / Responses DynamoDB tables.
#
# ADMIN-ONLY: this scans the tables (--max-items 20). A scan is fine for an
# occasional admin peek but is NOT a hot path — the app uses the ip_address-index
# GSI for its lookups, never a scan.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

require_cmd aws

for t in "$QUERIES_TABLE" "$RESPONSES_TABLE"; do
  info "Recent rows from $t (up to 20):"
  aws dynamodb scan \
    --region "$AWS_REGION" \
    --table-name "$t" \
    --max-items 20 \
    --output json
  echo
done
