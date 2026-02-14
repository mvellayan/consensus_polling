#!/bin/bash

# Configuration
APP_NAME="ai-supreme-court"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "🗑️ Removing AI Supreme Court from AWS Fargate..."

# Delete ECS service
echo "🚫 Deleting ECS service..."
aws ecs update-service \
  --cluster ${APP_NAME}-cluster \
  --service ${APP_NAME}-service \
  --desired-count 0 \
  --region ${REGION} 2>/dev/null

aws ecs delete-service \
  --cluster ${APP_NAME}-cluster \
  --service ${APP_NAME}-service \
  --region ${REGION} 2>/dev/null || echo "Service not found"

# Delete ECS cluster
echo "🗑️ Deleting ECS cluster..."
aws ecs delete-cluster \
  --cluster ${APP_NAME}-cluster \
  --region ${REGION} 2>/dev/null || echo "Cluster not found"

# Delete API Gateway
echo "🌐 Deleting API Gateway..."
API_IDS=$(aws apigatewayv2 get-apis --query "Items[?Name=='${APP_NAME}-api'].ApiId" --output text --region ${REGION})
for API_ID in $API_IDS; do
  if [ "$API_ID" != "None" ] && [ -n "$API_ID" ]; then
    aws apigatewayv2 delete-api --api-id ${API_ID} --region ${REGION}
  fi
done

# Delete Load Balancer
echo "⚖️ Deleting Application Load Balancer..."
ALB_ARN=$(aws elbv2 describe-load-balancers --names ${APP_NAME}-alb --query 'LoadBalancers[0].LoadBalancerArn' --output text --region ${REGION} 2>/dev/null)
if [ "$ALB_ARN" != "None" ] && [ -n "$ALB_ARN" ]; then
  aws elbv2 delete-load-balancer --load-balancer-arn ${ALB_ARN} --region ${REGION}
fi

# Delete Target Group
echo "🎯 Deleting target group..."
TG_ARN=$(aws elbv2 describe-target-groups --names ${APP_NAME}-tg --query 'TargetGroups[0].TargetGroupArn' --output text --region ${REGION} 2>/dev/null)
if [ "$TG_ARN" != "None" ] && [ -n "$TG_ARN" ]; then
  aws elbv2 delete-target-group --target-group-arn ${TG_ARN} --region ${REGION}
fi

# Delete Security Group
echo "🔒 Deleting security group..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text --region ${REGION})
SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${APP_NAME}-sg" --query 'SecurityGroups[0].GroupId' --output text --region ${REGION} 2>/dev/null)
if [ "$SG_ID" != "None" ] && [ -n "$SG_ID" ]; then
  aws ec2 delete-security-group --group-id ${SG_ID} --region ${REGION} 2>/dev/null || echo "Security group in use, will be deleted after dependencies"
fi

# Delete IAM roles and policies
echo "🔑 Deleting IAM roles..."
aws iam delete-role-policy \
  --role-name ${APP_NAME}-execution-role \
  --policy-name ParameterStoreAccess 2>/dev/null

aws iam delete-role-policy \
  --role-name ${APP_NAME}-task-role \
  --policy-name DocumentDBAccess 2>/dev/null

aws iam delete-role-policy \
  --role-name ${APP_NAME}-task-role \
  --policy-name DynamoDBAccess 2>/dev/null

aws iam detach-role-policy \
  --role-name ${APP_NAME}-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null

aws iam delete-role \
  --role-name ${APP_NAME}-execution-role 2>/dev/null || echo "Execution role not found"

aws iam delete-role \
  --role-name ${APP_NAME}-task-role 2>/dev/null || echo "Task role not found"

# Delete CloudWatch log group
echo "📊 Deleting CloudWatch log group..."
aws logs delete-log-group \
  --log-group-name /ecs/${APP_NAME} \
  --region ${REGION} 2>/dev/null || echo "Log group not found"

# Delete Parameter Store parameter
echo "🔐 Deleting Parameter Store parameter..."
aws ssm delete-parameter \
  --name "/${APP_NAME}/openai-api-key" \
  --region ${REGION} 2>/dev/null || echo "Parameter not found"

# Delete ECR repository
echo "📦 Deleting ECR repository..."
aws ecr delete-repository \
  --repository-name ${APP_NAME} \
  --force \
  --region ${REGION} 2>/dev/null || echo "Repository not found"

echo "✅ Cleanup complete!"
echo ""
echo "⚠️ Note: Some resources may take a few minutes to fully delete."
echo "   Security groups will be deleted automatically once load balancer is removed."
echo ""
echo "📊 DynamoDB tables were preserved:"
echo "   - scotus_queries"
echo "   - scotus_responses"
echo "   - scotus_job_progress"
echo ""
echo "To delete DynamoDB tables, run:"
echo "   aws dynamodb delete-table --table-name scotus_queries --region ${REGION}"
echo "   aws dynamodb delete-table --table-name scotus_responses --region ${REGION}"
echo "   aws dynamodb delete-table --table-name scotus_job_progress --region ${REGION}"
