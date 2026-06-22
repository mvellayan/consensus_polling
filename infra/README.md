# infra/ — ScotusStack (CDK Python)

Single stack `ScotusStack` deploying the SCOTUS Quart streaming app on
**Lambda response streaming** behind **CloudFront → Lambda Function URL (OAC)**
on the custom domain **scotus.run**.

## Resource graph

```
Route53 PublicHostedZone (scotus.run)
   └─ ACM cert (DNS-validated, us-east-1)
       └─ CloudFront (alias scotus.run, OAC, caching disabled, ALL_VIEWER_EXCEPT_HOST_HEADER)
           └─ Lambda Function URL (RESPONSE_STREAM, IAM auth)
               └─ Lambda scotus-app (python3.12 + Lambda Web Adapter layer, zip)
                   ├─ SSM SecureString /scotus/openai-api-key (read)
                   └─ DynamoDB scotusQueries / scotusResponses (read/write, GSI on ip_address)
```

## Prerequisites (one-time, operator)

1. **OpenAI key in SSM** — create the SecureString parameter the app reads:

   ```bash
   aws ssm put-parameter \
     --name /scotus/openai-api-key \
     --type SecureString \
     --value "sk-..." \
     --region us-east-1
   ```

2. **scotus.run nameservers → Route53** — the stack creates a `PublicHostedZone`
   for `scotus.run`. After the first deploy (or `cdk synth` + a manual zone),
   read the zone's four nameservers (output `HostedZoneNameServers` or the
   Route53 console) and set them as the **NS records at your domain registrar**.
   ACM DNS validation and the CloudFront alias only succeed once the registrar
   delegates to this zone.

## Deploy

```bash
cd infra
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

# Synthesize the CloudFormation template (no AWS calls):
cdk synth          # or: npx aws-cdk synth

# Bootstrap once per account/region, then deploy (us-east-1):
cdk bootstrap aws://<account-id>/us-east-1
cdk deploy
```

Everything is pinned to **us-east-1** because CloudFront's viewer certificate
(ACM) must live there.

## Notes / assumptions

- **Lambda Web Adapter layer version** (`LWA_LAYER_VERSION` in
  `scotus_stack.py`) may need bumping — verify the current version at
  https://github.com/awslabs/aws-lambda-web-adapter/releases . The ARN
  account (`753240598075`) and layer name (`LambdaAdapterLayerX86`) are stable.
- The Lambda is packaged from the **repo root** (the Quart app), excluding
  `scotus/`, `.venv/`, `infra/`, `tests/`, `.git/`, `__pycache__/`, `*.db`,
  `*.zip`, `*.md`, `.idea/`, `.claude/`. The app's start command is `run.sh`
  (`exec hypercorn app:app -b 0.0.0.0:8080`) — created by the app task.
- The Function URL is **IAM-authed** and CloudFront signs requests with an
  **Origin Access Control (OAC)**. The OAC is attached to the L2
  `FunctionUrlOrigin` via an escape hatch because the construct doesn't yet
  expose an OAC prop directly.
- DynamoDB tables use `RemovalPolicy.RETAIN` and `PAY_PER_REQUEST`. Each has a
  `ip_address-index` GSI so the app can replace its full-table scans.

## Smoke test the stream

After deploy, hit the raw `FunctionUrl` output (bypassing CloudFront) with SigV4
auth, then verify `https://scotus.run` once DNS/ACM propagate.
