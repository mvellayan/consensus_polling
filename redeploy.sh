#!/bin/bash

APP_NAME="ai-supreme-court"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}"

echo "🔄 Redeploying with fixes..."

# Login to ECR
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_REPO}

# Build and push new image
docker build -t ${APP_NAME} .
docker tag ${APP_NAME}:latest ${ECR_REPO}:latest
docker push ${ECR_REPO}:latest

# Force new deployment
aws ecs update-service \
  --cluster ${APP_NAME}-cluster \
  --service ${APP_NAME}-service \
  --force-new-deployment \
  --region ${REGION}

echo "✅ Redeployment initiated. Check logs with:"
echo "aws logs tail /ecs/${APP_NAME} --follow --region ${REGION}"
