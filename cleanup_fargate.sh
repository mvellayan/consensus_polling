#!/bin/bash

# Configuration
APP_NAME="ai-supreme-court"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "🧹 Cleaning up AWS resources for ${APP_NAME}..."

# Delete ECS service
echo "🗑️ Deleting ECS service..."
aws ecs update-service --cluster ${APP_NAME}-cluster --service ${APP_NAME}-service --desired-count 0 --region ${REGION} 2>/dev/null
aws ecs delete-service --cluster ${APP_NAME}-cluster --service ${APP_NAME}-service --region ${REGION} 2>/dev/null

# Delete ECS cluster
echo "🗑️ Deleting ECS cluster..."
aws ecs delete-cluster --cluster ${APP_NAME}-cluster --region ${REGION} 2>/dev/null

# Delete API Gateway
echo "🗑️ Deleting API Gateway..."
API_ID=$(aws apigatewayv2 get-apis --query "Items[?Name=='${APP_NAME}-api'].ApiId" --output text --region ${REGION} 2>/dev/null)
if [ ! -z "$API_ID" ]; then
  aws apigatewayv2 delete-api --api-id ${API_ID} --region ${REGION}
fi

# Delete Load Balancer
echo "🗑️ Deleting Load Balancer..."
ALB_ARN=$(aws elbv2 describe-load-balancers --names ${APP_NAME}-alb --query 'LoadBalancers[0].LoadBalancerArn' --output text --region ${REGION} 2>/dev/null)
if [ ! -z "$ALB_ARN" ] && [ "$ALB_ARN" != "None" ]; then
  aws elbv2 delete-load-balancer --load-balancer-arn ${ALB_ARN} --region ${REGION}
fi

# Delete Target Group
echo "🗑️ Deleting Target Group..."
TG_ARN=$(aws elbv2 describe-target-groups --names ${APP_NAME}-tg --query 'TargetGroups[0].TargetGroupArn' --output text --region ${REGION} 2>/dev/null)
if [ ! -z "$TG_ARN" ] && [ "$TG_ARN" != "None" ]; then
  aws elbv2 delete-target-group --target-group-arn ${TG_ARN} --region ${REGION}
fi

# Delete Security Group
echo "🗑️ Deleting Security Group..."
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${APP_NAME}-sg" --query 'SecurityGroups[0].GroupId' --output text --region ${REGION} 2>/dev/null)
if [ ! -z "$SG_ID" ] && [ "$SG_ID" != "None" ]; then
  aws ec2 delete-security-group --group-id ${SG_ID} --region ${REGION}
fi

# Delete IAM roles
echo "🗑️ Deleting IAM roles..."
aws iam detach-role-policy --role-name ${APP_NAME}-execution-role --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null
aws iam delete-role --role-name ${APP_NAME}-execution-role 2>/dev/null
aws iam delete-role --role-name ${APP_NAME}-task-role 2>/dev/null

# Delete CloudWatch log group
echo "🗑️ Deleting CloudWatch log group..."
aws logs delete-log-group --log-group-name /ecs/${APP_NAME} --region ${REGION} 2>/dev/null

# Delete Parameter Store parameter
echo "🗑️ Deleting Parameter Store parameter..."
aws ssm delete-parameter --name "/${APP_NAME}/openai-api-key" --region ${REGION} 2>/dev/null

# Delete ECR repository
echo "🗑️ Deleting ECR repository..."
aws ecr delete-repository --repository-name ${APP_NAME} --force --region ${REGION} 2>/dev/null

echo "✅ Cleanup complete!"
