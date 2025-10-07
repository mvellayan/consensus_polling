#!/bin/bash

APP_NAME="ai-supreme-court"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}"

echo "🏗️ Simple Docker build..."

# Login to ECR
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_REPO}

# Regular docker build (should work on any platform)
docker build -t ${APP_NAME} .
docker tag ${APP_NAME}:latest ${ECR_REPO}:latest
docker push ${ECR_REPO}:latest

# Force new deployment
aws ecs update-service \
  --cluster ${APP_NAME}-cluster \
  --service ${APP_NAME}-service \
  --force-new-deployment \
  --region ${REGION}

echo "✅ Simple build deployed!"
