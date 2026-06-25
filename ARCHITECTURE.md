# Architecture — consensus_polling (scotus.run)

The living description of how the system is built and why. For step-by-step
deploy commands see [`docs/deploy.md`](docs/deploy.md). The `*_PLAN.md` files at
the repo root are historical planning snapshots and are **superseded** by this
document.

Last verified: 2026-06-23.

---

## What it is

An "AI Supreme Court." A user asks a yes/no constitutional question; nine AI
"justices" — each grounded in that real justice's opinions — answer
independently and in parallel. The app classifies each answer
(Support / Overturn / Remand, plus Certainty & Scope axes), computes the vote
tally in code, and streams a plain-English **syllabus** that synthesizes the
ruling. Everything streams token-by-token to the browser.

Live at **https://scotus.run**.

---

## Request flow (end to end)

```
Browser (static/script.js)
   │  POST /api/query  {question, judges[]}   — reads NDJSON stream
   ▼
CloudFront  (scotus.run, ACM cert, injects X-Origin-Secret on every origin request)
   │
   ▼
Lambda Function URL  (AuthType NONE, InvokeMode RESPONSE_STREAM)
   │
   ▼
Lambda  (python3.12, x86_64, 1024 MB, 300 s)
   ├─ Lambda Web Adapter layer  → runs uvicorn → Quart ASGI app (app.py)
   │
   ├─ before_request: reject if X-Origin-Secret missing/wrong (403), /health exempt
   ├─ rate-limit check (per-IP 10/hr, global 1000/day) — BEFORE any OpenAI call
   ├─ fan out 9 asyncio tasks, one per justice:
   │      OpenAI Responses API (gpt-5, stream=True, reasoning=low,
   │      file_search over that justice's vector store)
   ├─ multiplex all judge tokens into one NDJSON stream via an asyncio.Queue
   ├─ compute the tally IN CODE (calculate_summary) → emit `tally`
   ├─ stream the grounded syllabus (gpt-5, reasoning=low) over the same response
   ├─ heartbeat task emits `ping` every 3 s so the stream never idles
   └─ durable write of the query + responses to DynamoDB, then `done`
```

A typical 9-judge query streams for ~45 s (warm). The whole thing is one
long-lived streaming HTTP response.

---

## Components

### Frontend — `static/script.js`, `templates/`
- Single page rendered by Quart. JS opens a `fetch` to `/api/query` and reads
  the **NDJSON** body with a `ReadableStream` reader, buffering partial lines.
- Renders a card per justice (fills in as tokens arrive), a color-coded summary
  bar, and the syllabus block. Shows `IP: <addr> · N queries`.
- **Retries once** if the request fails *before any data arrives* (the
  reused-connection reset case); a mid-stream failure is not retried.

### App — `app.py` (Quart + uvicorn)
- Async Quart app served by **uvicorn** (single worker) under the Lambda Web
  Adapter. uvicorn, not hypercorn — hypercorn's multiprocessing `SemLock` fails
  on Lambda (no `/dev/shm` named semaphores).
- Routes: `GET /` (page), `GET /health` (uptime, secret-exempt),
  `GET /api/judges`, `GET /api/check-limit`, `GET /api/total-queries`,
  `POST /api/query` (the streaming endpoint).
- Per-justice call: OpenAI **Responses API**, `model=gpt-5`,
  `reasoning={"effort":"low"}`, `stream=True`, with a `file_search` tool over
  the justice's own vector store. Output is capped to keep cards concise.
- Module init fetches the OpenAI key from SSM; reads `ORIGIN_SECRET` and the
  rate-limit env vars.

### Data layer — `dynamodb_util.py`
- Sync boto3 wrapped in `asyncio.to_thread(...)` so the event loop never blocks.
- `scotusQueries` / `scotusResponses` (partition key `ipaddress_timestamp`).
- Per-IP display count via the `ip_address-index` GSI (no table scans). Global
  display total via an atomic `__total__` counter item.
- Rate limiting via atomic, TTL'd counter items (`RATE#IP#<ip>#<hour>`,
  `RATE#GLOBAL#<day>`) in the same table — they carry no `ip_address`, so they
  stay out of the GSI and never pollute the display count.

### Infrastructure — `infra/` (AWS CDK, Python)
- `infra/scotus_stack.py` defines the whole stack. `cdk.json` runs
  `.venv/bin/python app.py` so the infra venv (not ambient python) is used.
- Lambda code is built by **Docker bundling** in the `sam/build-python3.12`
  image with `platform=linux/amd64` (Mac is arm64; the wheels must match x86_64
  Lambda or `pydantic_core` fails to load). boto3/botocore are stripped
  (runtime-provided). `scotus/judge_assistants.json` is packaged in.

---

## Streaming protocol (NDJSON)

One JSON object per line over the `/api/query` response body:

| event | meaning |
|---|---|
| `token` | a judge answer delta (`{judge, text}`) |
| `judge_done` | a judge finished (`{judge, outcome, certainty, scope, full_response}`) |
| `judge_error` | a judge call failed (additive — others continue) |
| `tally` | the code-computed vote grouping `{support[], overturn[], remand[]}` |
| `syllabus_token` | a delta of the synthesized plain-English ruling |
| `syllabus_error` | syllabus synthesis failed (additive) |
| `ping` | heartbeat; frontend ignores it |
| `done` | terminal event, always emitted (even on client disconnect) |

Internally the generator uses sentinel messages (`__done__` per judge,
`__syllabus_done__`) on a shared `asyncio.Queue` to drain deterministically — no
timeout polling.

---

## Grounding, classification & synthesis

- **Grounding:** each justice has its own OpenAI **vector store**
  (`vector_store_id` in `scotus/judge_assistants.json`); `file_search` retrieves
  the relevant opinion chunks per query. The nine justices are: alito, barrett,
  gorsuch, jackson, kagan, kavanaugh, roberts, sotomayor, thomas.
- **Outcome:** the first response line must be exactly `Support`, `Overturn`, or
  `Remand`, judged about the government action in the question
  (unconstitutional / not-permitted → **Overturn**, never Support). Parsed by
  `analyze_support_level`.
- **Axes:** line 2 carries Certainty (Definitive/Likely/Qualified/Conditional)
  and Scope (Broad/Narrow/Facial/As-Applied), parsed defensively by
  `parse_certainty_scope` (tolerates dropped labels).
- **Tally is computed in code** (`calculate_summary`) — never by the LLM. The
  syllabus model is *given* the tally as fixed fact and only writes prose, so it
  can't miscount the vote.

---

## Security

The Function URL is public (`AuthType NONE`) because OAC SigV4 signing is
rejected on a `RESPONSE_STREAM` Function URL. Two defenses compensate:

1. **Origin secret.** CloudFront injects `X-Origin-Secret` (a value stored in
   SSM `/scotus/origin-secret`, wired by `aws/_lib.sh` to both CloudFront and the
   Lambda env) on every origin request. `app.before_request` returns 403 for any
   request lacking it, so the raw Function URL can't be hit directly — all
   traffic must pass through CloudFront. `/health` is exempt for monitoring; the
   guard is a no-op locally (secret unset).
2. **Rate limits**, checked before any OpenAI spend: **per-IP 10/hour** and a
   **global 1000/day** cap. The global cap is the real wallet ceiling — it bounds
   cost (~$150/day max) regardless of IP rotation. Fails **open** (a DynamoDB
   blip never blocks real users). Tunable via `RATE_PER_IP_HOUR` /
   `RATE_GLOBAL_DAY`.

---

## Key constraints & decisions

- **~60 s streamed-response cap.** There is a hard ceiling (~60 s) on a single
  streamed response, observed at the Lambda/Function-URL level — it is *not* the
  300 s function timeout and *not* CloudFront's read timeout (a raw Function URL
  hit cuts at the same point, and the heartbeat proves it's a duration cap, not
  an idle one). The syllabus streams *after* all nine judges, so a slow run loses
  it. **Mitigation:** `reasoning=low` keeps a 9-judge run + syllabus to ~45 s
  warm (well under the cap); a cold-start first query is ~59 s and can clip the
  (additive) syllabus.
- **Model = gpt-5 at `low` effort.** gpt-5 (vs the earlier gpt-5-nano) gives
  consistent outcomes; `low` (vs `medium`) is required to fit the time cap. Each
  query costs roughly ~12–18¢ in tokens.
- **No connection keep-alive tuning.** `--timeout-keep-alive 0` was tried and
  reverted — it cut long streams during the syllabus reasoning gap. Reused-
  connection resets are handled by the frontend retry instead.
- **Client IP** is read from `CloudFront-Viewer-Address` (CloudFront's own
  measurement, not viewer-spoofable), falling back to `X-Forwarded-For`.

---

## Deploy & ops

- First-time provision: `sh ./aws/create.sh` (seeds SSM, bootstraps CDK,
  deploys, prints the registrar nameserver reminder).
- Code/infra changes: `sh ./aws/redeploy.sh` (re-bundles via Docker + applies
  the diff). **Docker must be running.**
- Other ops scripts: `aws/status.sh`, `aws/show_log.sh`, `aws/destroy.sh`.
- Logs: `aws logs tail /aws/lambda/scotus-app --since 5m`.
- Judge setup (paid OpenAI step, prerequisite for first deploy):
  `admin/init_judges.sh` builds the per-justice vector stores and writes
  `scotus/judge_assistants.json`.
- Stack: `ScotusStack` in `us-east-1` (CloudFront's ACM cert must live there).
  Function name `scotus-app`. CloudFront distribution `E1P5KJ0WLZKRD1`.

### Config & secrets
| where | what |
|---|---|
| SSM `/scotus/openai-api-key` (SecureString) | OpenAI key, fetched at startup |
| SSM `/scotus/origin-secret` (String) | CloudFront↔app shared secret |
| Lambda env | `ORIGIN_SECRET`, `RATE_PER_IP_HOUR=10`, `RATE_GLOBAL_DAY=1000`, table names, Web Adapter (`AWS_LWA_INVOKE_MODE=response_stream`) |

---

## Known limitations / future work

- **Cold-start margin.** The first query after idle runs close to the 60 s cap.
  A free "warmer" ping (EventBridge → synthetic `GET /health` every 5 min) **is
  implemented** in `infra/scotus_stack.py` to keep one execution environment warm
  and is effectively free (~8,640 invokes/mo, inside the Lambda free tier). It
  reduces cold starts but does not *raise* the cap; a hard latency guarantee
  would still need Provisioned Concurrency (~$11/mo), which is not implemented.
- **The 60 s cap** ultimately blocks deeper (`medium`/`high`) reasoning for
  9-judge runs. Raising it would need an architectural change (don't gate the
  syllabus on one 60 s response) or an AWS quota path.
- **Alternative model backend.** A migration to Claude (opinions-in-context +
  prompt caching, or a retrieval layer) was scoped as a future option for higher
  persona fidelity; not adopted.
- Legacy Fargate-era files and one orphan Route53 zone remain to be cleaned up.
