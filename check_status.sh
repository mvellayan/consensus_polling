#!/bin/bash

APP_NAME="ai-supreme-court"
REGION="us-east-1"

echo "🔍 Checking ECS service status..."

# Check service status
aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION} --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Events:events[0:3]}'

echo -e "\n🔍 Checking tasks..."
# Check task status
aws ecs list-tasks --cluster ${APP_NAME}-cluster --service-name ${APP_NAME}-service --region ${REGION} --query 'taskArns[0]' --output text | xargs -I {} aws ecs describe-tasks --cluster ${APP_NAME}-cluster --tasks {} --region ${REGION} --query 'tasks[0].{LastStatus:lastStatus,HealthStatus:healthStatus,StoppedReason:stoppedReason}'

echo -e "\n📊 Recent logs..."
# Get recent logs
aws logs tail /ecs/${APP_NAME} --region ${REGION} --since 5m
