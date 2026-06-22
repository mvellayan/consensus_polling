#!/usr/bin/env python3
"""CDK app entrypoint for the SCOTUS streaming web app.

CloudFront and ACM (for the viewer certificate) must live in us-east-1, so we
pin the whole stack there for now. The Lambda Function URL, DynamoDB tables and
Route53 hosted zone all live happily in us-east-1 too.
"""
import aws_cdk as cdk

from scotus_stack import ScotusStack

app = cdk.App()

ScotusStack(
    app,
    "ScotusStack",
    # CloudFront + ACM viewer cert require us-east-1.
    env=cdk.Environment(region="us-east-1"),
    description="Lambda response-streaming SCOTUS app behind CloudFront on scotus.me",
)

app.synth()
