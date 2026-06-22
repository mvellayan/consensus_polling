"""ScotusStack — Lambda response-streaming web app on scotus.me.

Resource graph:

  Route53 PublicHostedZone (scotus.me)
        │  (operator points registrar NS here)
        ▼
  ACM Certificate (scotus.me, DNS-validated, us-east-1)
        │
        ▼
  CloudFront Distribution (alias scotus.me, OAC) ──► Lambda Function URL
                                                     (RESPONSE_STREAM, IAM auth)
                                                            │
                                                            ▼
                                              Lambda (python3.12 + Web Adapter)
                                              ── reads SSM /scotus/openai-api-key
                                              ── read/write DynamoDB Queries+Responses
                                                            │
                                                            ▼
                                  DynamoDB: <prefix>Queries, <prefix>Responses
                                            (PAY_PER_REQUEST, GSI on ip_address)
"""
import os

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    RemovalPolicy,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_certificatemanager as acm,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_ssm as ssm,
)
from constructs import Construct

# Repo root is the parent of this infra/ directory; it holds the Quart app.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Domain served by CloudFront.
DOMAIN_NAME = "scotus.me"

# Logical name prefix for the DynamoDB tables; overridable via the app env var
# TABLE_PREFIX at runtime, but the physical table names are fixed at deploy time
# so the app can address them deterministically.
TABLE_PREFIX = "scotus"

# AWS Lambda Web Adapter public layer (x86_64).
# Account 753240598075 is the AWS-published layer account.
# NOTE: layer version below ("25") MAY NEED UPDATING — verify the current
# version at https://github.com/awslabs/aws-lambda-web-adapter/releases
# (the ARN account/name pattern is stable; only the trailing version moves).
LWA_LAYER_VERSION = 25


class ScotusStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        queries_table_name = f"{TABLE_PREFIX}Queries"
        responses_table_name = f"{TABLE_PREFIX}Responses"

        # ------------------------------------------------------------------
        # DynamoDB tables (fresh, parameterized names).
        # Partition key matches the app: ipaddress_timestamp (String).
        # GSI on ip_address replaces the app's full-table scans.
        # ------------------------------------------------------------------
        queries_table = dynamodb.Table(
            self,
            "QueriesTable",
            table_name=queries_table_name,
            partition_key=dynamodb.Attribute(
                name="ipaddress_timestamp", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )
        queries_table.add_global_secondary_index(
            index_name="ip_address-index",
            partition_key=dynamodb.Attribute(
                name="ip_address", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        responses_table = dynamodb.Table(
            self,
            "ResponsesTable",
            table_name=responses_table_name,
            partition_key=dynamodb.Attribute(
                name="ipaddress_timestamp", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
        )
        responses_table.add_global_secondary_index(
            index_name="ip_address-index",
            partition_key=dynamodb.Attribute(
                name="ip_address", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ------------------------------------------------------------------
        # SSM SecureString holding the OpenAI API key.
        # The parameter VALUE is created out-of-band by the operator (see README);
        # CDK only references it and grants read.
        # ------------------------------------------------------------------
        openai_param = ssm.StringParameter.from_secure_string_parameter_attributes(
            self,
            "OpenAiApiKeyParam",
            parameter_name="/scotus/openai-api-key",
        )

        # ------------------------------------------------------------------
        # Lambda Web Adapter layer (public).
        # ------------------------------------------------------------------
        lwa_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "LambdaWebAdapterLayer",
            f"arn:aws:lambda:{self.region}:753240598075:"
            f"layer:LambdaAdapterLayerX86:{LWA_LAYER_VERSION}",
        )

        # ------------------------------------------------------------------
        # Lambda function — the Quart app, packaged as a zip from the repo root.
        # Web Adapter runs `run.sh` (hypercorn) and bridges Function URL streaming
        # to the local ASGI server on port 8080.
        # ------------------------------------------------------------------
        app_fn = _lambda.Function(
            self,
            "ScotusAppFunction",
            function_name="scotus-app",
            runtime=_lambda.Runtime.PYTHON_3_12,
            architecture=_lambda.Architecture.X86_64,
            # Web Adapter wraps the process; `handler` is the start command file.
            handler="run.sh",
            code=_lambda.Code.from_asset(
                REPO_ROOT,
                exclude=[
                    "scotus",
                    ".venv",
                    "infra",
                    "tests",
                    ".git",
                    "__pycache__",
                    "*.db",
                    "*.zip",
                    "*.md",
                    ".idea",
                    ".claude",
                ],
            ),
            layers=[lwa_layer],
            timeout=Duration.seconds(300),
            memory_size=1024,
            environment={
                # Web Adapter bootstrap + streaming config.
                "AWS_LAMBDA_EXEC_WRAPPER": "/opt/bootstrap",
                "AWS_LWA_INVOKE_MODE": "response_stream",
                "AWS_LWA_PORT": "8080",
                "PORT": "8080",
                # App config.
                "TABLE_PREFIX": TABLE_PREFIX,
                "QUERIES_TABLE": queries_table_name,
                "RESPONSES_TABLE": responses_table_name,
                # The app reads the key from SSM at runtime using this name.
                "OPENAI_API_KEY_PARAM": openai_param.parameter_name,
            },
        )

        # IAM: tables (incl. GSIs via grant) + SSM parameter read.
        queries_table.grant_read_write_data(app_fn)
        responses_table.grant_read_write_data(app_fn)
        openai_param.grant_read(app_fn)

        # ------------------------------------------------------------------
        # Function URL — response streaming, IAM-authed (signed by CloudFront OAC).
        # ------------------------------------------------------------------
        fn_url = app_fn.add_function_url(
            auth_type=_lambda.FunctionUrlAuthType.AWS_IAM,
            invoke_mode=_lambda.InvokeMode.RESPONSE_STREAM,
        )

        # CloudFront Origin Access Control so CloudFront SigV4-signs requests to
        # the IAM-protected Function URL.
        oac = cloudfront.CfnOriginAccessControl(
            self,
            "FunctionUrlOac",
            origin_access_control_config=cloudfront.CfnOriginAccessControl.OriginAccessControlConfigProperty(
                name="scotus-fn-url-oac",
                origin_access_control_origin_type="lambda",
                signing_behavior="always",
                signing_protocol="sigv4",
            ),
        )

        # ------------------------------------------------------------------
        # Route53 hosted zone (operator points the registrar's NS at this zone).
        # ------------------------------------------------------------------
        hosted_zone = route53.PublicHostedZone(
            self,
            "HostedZone",
            zone_name=DOMAIN_NAME,
        )

        # ------------------------------------------------------------------
        # ACM certificate for scotus.me, DNS-validated against the zone.
        # Stack is in us-east-1, so this cert is valid for CloudFront.
        # ------------------------------------------------------------------
        certificate = acm.Certificate(
            self,
            "Certificate",
            domain_name=DOMAIN_NAME,
            validation=acm.CertificateValidation.from_dns(hosted_zone),
        )

        # ------------------------------------------------------------------
        # CloudFront distribution.
        # Origin = Function URL domain (HTTPS). Streaming + no caching:
        #   - CachePolicy.CACHING_DISABLED
        #   - OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER
        #   - allow all viewer methods (incl. POST)
        # OAC is attached below via escape hatch (see note).
        # ------------------------------------------------------------------
        fn_url_origin = origins.FunctionUrlOrigin(fn_url)

        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=fn_url_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,  # incl. POST
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            ),
            domain_names=[DOMAIN_NAME],
            certificate=certificate,
            comment="SCOTUS streaming app",
        )

        # Attach the OAC to the Function URL origin via escape hatch — the L2
        # FunctionUrlOrigin doesn't yet expose an OAC prop, so we set the
        # OriginAccessControlId on the generated CloudFront origin and clear the
        # legacy (empty) OriginAccessControlId default.
        cfn_distribution = distribution.node.default_child
        cfn_distribution.add_property_override(
            "DistributionConfig.Origins.0.OriginAccessControlId",
            oac.get_att("Id"),
        )

        # Allow CloudFront (this distribution) to invoke the Function URL.
        app_fn.add_permission(
            "AllowCloudFrontInvoke",
            principal=cdk.aws_iam.ServicePrincipal("cloudfront.amazonaws.com"),
            action="lambda:InvokeFunctionUrl",
            function_url_auth_type=_lambda.FunctionUrlAuthType.AWS_IAM,
            source_arn=(
                f"arn:aws:cloudfront::{self.account}:distribution/"
                f"{distribution.distribution_id}"
            ),
        )

        # ------------------------------------------------------------------
        # Route53 alias records scotus.me -> CloudFront (A + AAAA).
        # ------------------------------------------------------------------
        route53.ARecord(
            self,
            "AliasRecordA",
            zone=hosted_zone,
            record_name=DOMAIN_NAME,
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution)
            ),
        )
        route53.AaaaRecord(
            self,
            "AliasRecordAAAA",
            zone=hosted_zone,
            record_name=DOMAIN_NAME,
            target=route53.RecordTarget.from_alias(
                targets.CloudFrontTarget(distribution)
            ),
        )

        # ------------------------------------------------------------------
        # Outputs.
        # ------------------------------------------------------------------
        CfnOutput(
            self,
            "AppUrl",
            value=f"https://{DOMAIN_NAME}",
            description="Public app URL",
        )
        CfnOutput(
            self,
            "CloudFrontDomain",
            value=distribution.distribution_domain_name,
            description="CloudFront distribution domain",
        )
        CfnOutput(
            self,
            "FunctionUrl",
            value=fn_url.url,
            description="Lambda Function URL (smoke-test the stream directly here)",
        )
        CfnOutput(
            self,
            "QueriesTableName",
            value=queries_table.table_name,
        )
        CfnOutput(
            self,
            "ResponsesTableName",
            value=responses_table.table_name,
        )
        CfnOutput(
            self,
            "HostedZoneNameServers",
            value=cdk.Fn.join(", ", hosted_zone.hosted_zone_name_servers or []),
            description="Point the scotus.me registrar nameservers at these",
        )
