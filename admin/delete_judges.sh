#!/usr/bin/env bash
# Delete judge resources.
#
#   admin/delete_judges.sh              Delete only the vector stores + files
#                                       listed in judge_assistants.json (safe default).
#   admin/delete_judges.sh --purge-all  ALSO delete EVERY vector store and EVERY
#                                       file in the entire OpenAI account.
#
# WARNING: --purge-all is an account-wide wipe. The original undeploy_judges.sh
# did this unconditionally; that is a footgun (it nukes resources unrelated to
# this app), so here it is opt-in only.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_lib.sh"

require_cmd python

PURGE_ALL=0
if [ "${1:-}" = "--purge-all" ]; then
  PURGE_ALL=1
elif [ -n "${1:-}" ]; then
  err "Unknown argument: $1 (expected --purge-all or nothing)"
  exit 1
fi

if [ -z "${OPENAI_API_KEY:-}" ]; then
  err "OPENAI_API_KEY not set. Put it in the repo-root .env."
  exit 1
fi

# --- Default: delete only what's recorded in judge_assistants.json ------------
info "Deleting judge vector stores + files listed in judge_assistants.json ..."
( cd "$ROOT_DIR" && python scotus/delete_judges.py )

if [ "$PURGE_ALL" -eq 0 ]; then
  ok "Done. (Use --purge-all to also wipe every vector store/file in the account.)"
  exit 0
fi

# --- Opt-in account-wide purge (the original footgun, now guarded) ------------
require_cmd curl jq

warn "ACCOUNT-WIDE PURGE: this deletes EVERY vector store and EVERY file in the"
warn "OpenAI account for this key — including resources unrelated to SCOTUS."
read -r -p "Type PURGE-ALL to continue: " ans
if [ "$ans" != "PURGE-ALL" ]; then
  err "Aborted account-wide purge."
  exit 1
fi

info "Deleting all vector stores ..."
vector_stores=$(curl -s https://api.openai.com/v1/vector_stores \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "OpenAI-Beta: assistants=v2" | jq -r '.data[]?.id // empty')
if [ -n "$vector_stores" ]; then
  for vs_id in $vector_stores; do
    info "Deleting vector store: $vs_id"
    curl -s -X DELETE "https://api.openai.com/v1/vector_stores/$vs_id" \
      -H "Authorization: Bearer $OPENAI_API_KEY" \
      -H "OpenAI-Beta: assistants=v2" >/dev/null
  done
else
  info "No vector stores found."
fi

info "Deleting all files ..."
files=$(curl -s https://api.openai.com/v1/files \
  -H "Authorization: Bearer $OPENAI_API_KEY" | jq -r '.data[]?.id // empty')
if [ -n "$files" ]; then
  for file_id in $files; do
    info "Deleting file: $file_id"
    curl -s -X DELETE "https://api.openai.com/v1/files/$file_id" \
      -H "Authorization: Bearer $OPENAI_API_KEY" >/dev/null
  done
else
  info "No files found."
fi

ok "Account-wide purge complete."
