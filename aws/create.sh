#!/usr/bin/env bash
# First-time provisioning of ScotusStack.
#
# Prerequisite: judge_assistants.json must exist BEFORE this deploy — it is
# packaged into the Lambda as a runtime input. Run `admin/init_judges.sh` first
# (paid OpenAI step) if it isn't present.
#
# Steps:
#   1. Seed the OpenAI key into the SSM SecureString param (from OPENAI_API_KEY).
#   2. pip install infra deps, cdk bootstrap, cdk deploy.
#   3. Print outputs + the registrar nameserver reminder.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

require_cmd aws npx pip

# --- 0. judge_assistants.json must be present (packaged into the Lambda) -------
if [ ! -f "$ROOT_DIR/scotus/judge_assistants.json" ]; then
  err "scotus/judge_assistants.json not found in $ROOT_DIR"
  err "Run admin/init_judges.sh first (paid OpenAI step) — it is a build prerequisite."
  exit 1
fi
ok "scotus/judge_assistants.json present"

# --- 1. Seed the OpenAI key into SSM ------------------------------------------
if [ -z "${OPENAI_API_KEY:-}" ]; then
  err "OPENAI_API_KEY is not set. Set it in aws/.env so create.sh can seed the SSM param."
  err "Param to create: ${OPENAI_API_KEY_PARAM:-/scotus/openai-api-key}"
  exit 1
fi

info "Seeding SSM SecureString ${OPENAI_API_KEY_PARAM:-/scotus/openai-api-key} ..."
aws ssm put-parameter \
  --region "$AWS_REGION" \
  --name "${OPENAI_API_KEY_PARAM:-/scotus/openai-api-key}" \
  --type SecureString \
  --value "$OPENAI_API_KEY" \
  --overwrite >/dev/null
ok "OpenAI key stored in SSM"

# --- 2. Install infra deps (into infra/.venv), bootstrap, deploy --------------
# cdk.json runs `.venv/bin/python app.py`, so the deps must live in that venv.
info "Installing infra dependencies (infra/.venv) ..."
( cd "$INFRA_DIR" && python3 -m venv .venv && ./.venv/bin/pip install -q -r requirements.txt )

info "Bootstrapping CDK (idempotent) ..."
( cd "$INFRA_DIR" && npx aws-cdk bootstrap )

info "Deploying $STACK_NAME ..."
( cd "$INFRA_DIR" && npx aws-cdk deploy --require-approval never )

# --- 3. Outputs + nameserver reminder -----------------------------------------
ok "Deploy complete. Stack outputs:"
echo "  AppUrl:           $(stack_output AppUrl)"
echo "  CloudFrontDomain: $(stack_output CloudFrontDomain)"
echo "  FunctionUrl:      $(stack_output FunctionUrl)"
echo "  QueriesTable:     $(stack_output QueriesTableName)"
echo "  ResponsesTable:   $(stack_output ResponsesTableName)"

echo
warn "NAMESERVER REMINDER"
warn "Point the ${APP_DOMAIN:-scotus.run} registrar's NS records at this hosted zone:"
echo "  $(stack_output HostedZoneNameServers)"
warn "ACM DNS validation and the CloudFront alias only succeed once the registrar"
warn "delegates to this Route53 zone."
