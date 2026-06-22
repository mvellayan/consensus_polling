# Deploying SCOTUS (scotus.me)

The AI Supreme Court runs as a single CDK stack, **`ScotusStack`**, deploying a
Quart streaming app on **Lambda response streaming** behind
**CloudFront → Lambda Function URL (OAC)** on the custom domain **scotus.me**.

This supersedes the stale `DEPLOYMENT_README.md` (Fargate-era) intent.

## Architecture (one paragraph)

A single Lambda (`scotus-app`, python3.12 + Lambda Web Adapter layer, zip-packaged)
holds one request open and **streams all 9 justices' tokens live**. CloudFront
(ACM cert in us-east-1, Origin Access Control) signs requests to an IAM-authed
**Function URL** running in `RESPONSE_STREAM` mode. The handler fans out 9
`AsyncOpenAI` streams (file_search per judge), multiplexes them through an
`asyncio.Queue`, computes the vote tally **in code**, then streams a grounded
syllabus. Rate limiting and the durable query/response log use two DynamoDB
tables (`scotusQueries`, `scotusResponses`, both with an `ip_address-index` GSI).
No daemon threads, no job-progress polling — the stream replaces all of it.

## Prerequisites (one-time, operator)

1. **`scotus.me` nameservers → Route53.** The stack creates a `PublicHostedZone`
   for `scotus.me`. After the first deploy, read the `HostedZoneNameServers`
   output and set those four NS records **at your domain registrar**. ACM DNS
   validation and the CloudFront alias only succeed once the registrar delegates
   to this zone.
2. **ACM cert in us-east-1.** Created automatically by CDK (DNS-validated against
   the hosted zone). Everything is pinned to us-east-1 because CloudFront's
   viewer certificate must live there.
3. **`OPENAI_API_KEY`.** Set it in `aws/.env` so `aws/create.sh` can seed the SSM
   SecureString `/scotus/openai-api-key` (the Lambda reads the key from SSM at
   runtime). Also set it in the repo-root `.env` for the `admin/` judge scripts.
4. **Run `admin/init_judges.sh` first.** This regenerates `judge_assistants.json`
   (a paid OpenAI step) — it is packaged into the Lambda and must exist *before*
   `aws/create.sh` runs.

## Command reference

### `aws/` — infrastructure / operations

| Script | What it does |
| --- | --- |
| `_lib.sh` | Shared helpers (sourced, never run). Loads `aws/.env`→`env.example`, sets region/stack, `stack_output`, `confirm`, color logging. |
| `create.sh` | First deploy: seeds the OpenAI key into SSM, `pip install` infra deps, `cdk bootstrap`, `cdk deploy`, prints outputs + the registrar nameserver reminder. |
| `redeploy.sh` | Re-deploy code changes (re-uploads the Lambda asset) without re-bootstrapping. |
| `status.sh` | CFN stack status, stack outputs, Lambda state, CloudFront distribution status, table item counts. |
| `show_log.sh [--since <dur>]` | Tail the `scotus-app` Lambda's CloudWatch logs (default window 10m). |
| `destroy.sh` | `cdk destroy` after typing `DESTROY`. RETAINed DynamoDB tables survive. |

### `admin/` — data / judge lifecycle

| Script | What it does |
| --- | --- |
| `_lib.sh` | Shared helpers (sourced). Loads repo-root `.env` for `OPENAI_API_KEY`. |
| `init_judges.sh` | Regenerate `judge_assistants.json` (paid OpenAI step, build prerequisite). |
| `delete_judges.sh [--purge-all]` | Delete the vector stores/files in `judge_assistants.json`. `--purge-all` (guarded) additionally wipes EVERY vector store/file in the account. |
| `query_history.sh` | Dump up to 20 recent rows from each DynamoDB table (admin-only scan, not a hot path). |

## First-deploy walkthrough

```bash
# 0. Config
cp aws/env.example aws/.env       # set OPENAI_API_KEY in aws/.env
echo 'OPENAI_API_KEY=sk-...' >> .env   # repo-root .env, for admin/ scripts

# 1. Generate the judges (paid; produces judge_assistants.json)
admin/init_judges.sh

# 2. First deploy (seeds SSM, bootstraps, deploys)
aws/create.sh

# 3. Point the scotus.me registrar NS records at the printed HostedZoneNameServers.
#    Wait for ACM DNS validation + CloudFront to settle.

# 4. Verify
aws/status.sh
#    Smoke the raw FunctionUrl (SigV4) first, then https://scotus.me once DNS/ACM propagate.

# Later: ship code changes
aws/redeploy.sh
```

## Stack reference (verbatim from infra/scotus_stack.py)

- Stack: `ScotusStack` (region us-east-1)
- Lambda: `scotus-app` — logs at `/aws/lambda/scotus-app`
- Tables: `scotusQueries`, `scotusResponses` (GSI `ip_address-index`, PAY_PER_REQUEST, RETAIN)
- SSM: `/scotus/openai-api-key` (SecureString)
- Outputs: `AppUrl`, `CloudFrontDomain`, `FunctionUrl`, `QueriesTableName`, `ResponsesTableName`, `HostedZoneNameServers`

## Known limitation

If the client disconnects mid-stream (closes the tab), that run's live output is
lost for the user — there is no resumable stream. The durable log still records
it: the handler's `finally` block writes whatever completed to DynamoDB, so the
query is never silently dropped. Resumable streams are explicitly out of scope.
