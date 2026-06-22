#!/usr/bin/env bash
# Initialize the 9 judge vector stores and (re)generate judge_assistants.json.
#
# PAID STEP: this uploads documents and creates OpenAI vector stores — it costs
# money. It is also a BUILD PREREQUISITE: judge_assistants.json must exist before
# aws/create.sh / aws/redeploy.sh package the Lambda.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

require_cmd python

if [ -z "${OPENAI_API_KEY:-}" ]; then
  err "OPENAI_API_KEY not set. Put it in the repo-root .env."
  exit 1
fi

warn "This is a PAID OpenAI step (uploads + vector store creation)."
info "Regenerating judge_assistants.json via initialize_judges.py ..."
( cd "$ROOT_DIR" && python scotus/initialize_judges.py )

ok "judge_assistants.json regenerated. You can now run aws/create.sh / aws/redeploy.sh."
