#!/usr/bin/env bash
# Read-only health snapshot of ScotusStack: CFN status, outputs, Lambda state,
# CloudFront distribution status, and (best-effort) table item counts.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

require_cmd aws

# --- CloudFormation stack status ----------------------------------------------
status=$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].StackStatus" \
  --output text 2>/dev/null || true)

if [ -z "$status" ]; then
  err "Stack $STACK_NAME not found in $AWS_REGION. Run aws/create.sh first."
  exit 1
fi
info "Stack $STACK_NAME: $status"

# --- Outputs ------------------------------------------------------------------
app_url=$(stack_output AppUrl)
cf_domain=$(stack_output CloudFrontDomain)
fn_url=$(stack_output FunctionUrl)
queries_table=$(stack_output QueriesTableName)
responses_table=$(stack_output ResponsesTableName)
nameservers=$(stack_output HostedZoneNameServers)

echo "  AppUrl:           $app_url"
echo "  CloudFrontDomain: $cf_domain"
echo "  FunctionUrl:      $fn_url"
echo "  QueriesTable:     $queries_table"
echo "  ResponsesTable:   $responses_table"
echo "  NameServers:      $nameservers"

# --- Lambda function state ----------------------------------------------------
fn_name="scotus-app"
fn_state=$(aws lambda get-function \
  --region "$AWS_REGION" \
  --function-name "$fn_name" \
  --query "Configuration.[State,LastUpdateStatus]" \
  --output text 2>/dev/null || true)
if [ -n "$fn_state" ]; then
  ok "Lambda $fn_name: $fn_state"
else
  warn "Lambda $fn_name: not found"
fi

# --- CloudFront distribution status -------------------------------------------
if [ -n "$cf_domain" ]; then
  dist_id=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?DomainName=='$cf_domain'].Id | [0]" \
    --output text 2>/dev/null || true)
  if [ -n "$dist_id" ] && [ "$dist_id" != "None" ]; then
    dist_status=$(aws cloudfront get-distribution \
      --id "$dist_id" \
      --query "Distribution.Status" \
      --output text 2>/dev/null || true)
    ok "CloudFront $dist_id: ${dist_status:-unknown}"
  else
    warn "CloudFront distribution for $cf_domain: not found"
  fi
fi

# --- Table item counts (best-effort; ItemCount updates ~every 6h) -------------
for t in "$queries_table" "$responses_table"; do
  [ -z "$t" ] && continue
  count=$(aws dynamodb describe-table \
    --region "$AWS_REGION" \
    --table-name "$t" \
    --query "Table.ItemCount" \
    --output text 2>/dev/null || true)
  info "Table $t: ${count:-?} items (approximate)"
done
