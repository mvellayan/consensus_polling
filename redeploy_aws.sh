#!/bin/bash

# Configuration
APP_NAME="ai-supreme-court"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}"

echo "🔄 Redeploying AI Supreme Court application to AWS Fargate..."
echo ""

# Get ECR login token
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_REPO}

# Build and push Docker image
echo "🏗️  Building Docker image..."
docker build --platform linux/amd64 -t ${APP_NAME} .
docker tag ${APP_NAME}:latest ${ECR_REPO}:latest

echo "📤 Pushing to ECR..."
docker push ${ECR_REPO}:latest

# Check service status and fix if draining or stuck
echo "🔍 Checking service status..."
SERVICE_STATUS=$(aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION} --query 'services[0].status' --output text 2>/dev/null)

if [ "$SERVICE_STATUS" = "DRAINING" ] || [ "$SERVICE_STATUS" = "INACTIVE" ]; then
  echo "⚠️  Service is ${SERVICE_STATUS}. Recreating service..."
  
  # Get current service configuration
  TARGET_GROUP_ARN=$(aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION} --query 'services[0].loadBalancers[0].targetGroupArn' --output text)
  SUBNETS=$(aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION} --query 'services[0].networkConfiguration.awsvpcConfiguration.subnets' --output text | tr '\t' ',')
  SECURITY_GROUPS=$(aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION} --query 'services[0].networkConfiguration.awsvpcConfiguration.securityGroups' --output text)
  
  # Delete and recreate service
  aws ecs delete-service --cluster ${APP_NAME}-cluster --service ${APP_NAME}-service --force --region ${REGION} >/dev/null
  
  aws ecs create-service \
    --cluster ${APP_NAME}-cluster \
    --service-name ${APP_NAME}-service \
    --task-definition ${APP_NAME} \
    --desired-count 1 \
    --launch-type FARGATE \
    --load-balancers targetGroupArn=${TARGET_GROUP_ARN},containerName=${APP_NAME},containerPort=5000 \
    --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SECURITY_GROUPS}],assignPublicIp=ENABLED}" \
    --enable-execute-command \
    --region ${REGION} >/dev/null
  
  echo "✅ Service recreated successfully"
else
  # Check if deployment is stuck (IN_PROGRESS for too long)
  ROLLOUT_STATE=$(aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION} --query 'services[0].deployments[0].rolloutState' --output text 2>/dev/null)
  DEPLOYMENT_AGE=$(aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION} --query 'services[0].deployments[0].createdAt' --output text 2>/dev/null)
  
  if [ "$ROLLOUT_STATE" = "IN_PROGRESS" ]; then
    echo "⚠️  Deployment stuck IN_PROGRESS. Creating new service..."
    
    # Get current service configuration
    TARGET_GROUP_ARN=$(aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION} --query 'services[0].loadBalancers[0].targetGroupArn' --output text)
    SUBNETS=$(aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION} --query 'services[0].networkConfiguration.awsvpcConfiguration.subnets' --output text | tr '\t' ',')
    SECURITY_GROUPS=$(aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION} --query 'services[0].networkConfiguration.awsvpcConfiguration.securityGroups' --output text)
    
    # Create new service with v2 suffix
    aws ecs create-service \
      --cluster ${APP_NAME}-cluster \
      --service-name ${APP_NAME}-service-v2 \
      --task-definition ${APP_NAME} \
      --desired-count 1 \
      --launch-type FARGATE \
      --load-balancers targetGroupArn=${TARGET_GROUP_ARN},containerName=${APP_NAME},containerPort=5000 \
      --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SECURITY_GROUPS}],assignPublicIp=ENABLED}" \
      --enable-execute-command \
      --region ${REGION} >/dev/null
    
    echo "✅ New service created: ${APP_NAME}-service-v2"
  else
    # Force new deployment of ECS service
    echo "🚀 Forcing new deployment of ECS service..."
    aws ecs update-service \
      --cluster ${APP_NAME}-cluster \
      --service ${APP_NAME}-service \
      --force-new-deployment \
      --region ${REGION} >/dev/null
  fi
fi

echo ""
echo "✅ Redeployment initiated!"
echo ""
echo "📊 Monitor deployment progress:"
echo "   aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION} --query 'services[0].deployments'"
echo ""
echo "📋 Watch logs:"
echo "   aws logs tail /ecs/${APP_NAME} --follow --region ${REGION}"
echo ""
echo "⏳ The new task will take 2-3 minutes to start..."
