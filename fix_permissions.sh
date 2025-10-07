#!/bin/bash

APP_NAME="ai-supreme-court"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "🔧 Fixing IAM permissions..."

# Create policy for Parameter Store access
cat > ssm-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameters",
                "ssm:GetParameter"
            ],
            "Resource": "arn:aws:ssm:${REGION}:${ACCOUNT_ID}:parameter/${APP_NAME}/*"
        }
    ]
}
EOF

# Create and attach the policy
aws iam create-policy \
    --policy-name ${APP_NAME}-ssm-policy \
    --policy-document file://ssm-policy.json 2>/dev/null || echo "Policy already exists"

aws iam attach-role-policy \
    --role-name ${APP_NAME}-execution-role \
    --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/${APP_NAME}-ssm-policy

# Force service update to restart tasks
aws ecs update-service \
    --cluster ${APP_NAME}-cluster \
    --service ${APP_NAME}-service \
    --force-new-deployment \
    --region ${REGION}

rm ssm-policy.json

echo "✅ Permissions fixed. Service restarting..."
echo "Check status in 2 minutes with: ./check_status.sh"
