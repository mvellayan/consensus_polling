#!/bin/bash

# Configuration
APP_NAME="ai-supreme-court"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}"

echo "🚀 Deploying AI Supreme Court to AWS Fargate..."

# Create ECR repository
echo "📦 Creating ECR repository..."
aws ecr create-repository --repository-name ${APP_NAME} --region ${REGION} 2>/dev/null || echo "Repository already exists"

# Get ECR login token
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_REPO}

# Build and push Docker image
echo "🏗️ Building Docker image..."
docker build --platform linux/amd64 -t ${APP_NAME} .
docker tag ${APP_NAME}:latest ${ECR_REPO}:latest

echo "📤 Pushing to ECR..."
docker push ${ECR_REPO}:latest

# Create ECS cluster
echo "🏗️ Creating ECS cluster..."
aws ecs create-cluster --cluster-name ${APP_NAME}-cluster --region ${REGION}

# Create IAM role for ECS task execution
echo "🔑 Creating IAM roles..."
cat > task-execution-role-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name ${APP_NAME}-execution-role \
  --assume-role-policy-document file://task-execution-role-trust-policy.json 2>/dev/null || echo "Execution role already exists"

aws iam attach-role-policy \
  --role-name ${APP_NAME}-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

# Add Parameter Store permissions to execution role
cat > parameter-store-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameters"
      ],
      "Resource": "arn:aws:ssm:${REGION}:${ACCOUNT_ID}:parameter/${APP_NAME}/*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name ${APP_NAME}-execution-role \
  --policy-name ParameterStoreAccess \
  --policy-document file://parameter-store-policy.json

# Create task role for the application
cat > task-role-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

aws iam create-role \
  --role-name ${APP_NAME}-task-role \
  --assume-role-policy-document file://task-role-trust-policy.json 2>/dev/null || echo "Task role already exists"

# Add DocumentDB permissions to task role
cat > documentdb-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "docdb:DescribeDBClusters",
        "docdb:DescribeDBInstances",
        "docdb:ListTagsForResource",
        "docdb:Connect"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "docdb-elastic:GetCluster",
        "docdb-elastic:ListClusters"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeNetworkInterfaces",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups"
      ],
      "Resource": "*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name ${APP_NAME}-task-role \
  --policy-name DocumentDBAccess \
  --policy-document file://documentdb-policy.json

# Create DynamoDB tables
echo "📊 Creating DynamoDB tables..."

# Create scotus_queries table
aws dynamodb create-table \
  --table-name scotus_queries \
  --attribute-definitions AttributeName=ipaddress_timestamp,AttributeType=S \
  --key-schema AttributeName=ipaddress_timestamp,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ${REGION} 2>/dev/null || echo "scotus_queries table already exists"

# Create scotus_responses table
aws dynamodb create-table \
  --table-name scotus_responses \
  --attribute-definitions AttributeName=ipaddress_timestamp,AttributeType=S \
  --key-schema AttributeName=ipaddress_timestamp,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ${REGION} 2>/dev/null || echo "scotus_responses table already exists"

# Create scotus_job_progress table
aws dynamodb create-table \
  --table-name scotus_job_progress \
  --attribute-definitions AttributeName=job_id,AttributeType=S \
  --key-schema AttributeName=job_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --time-to-live-specification Enabled=true,AttributeName=ttl \
  --region ${REGION} 2>/dev/null || echo "scotus_job_progress table already exists"

# Add DynamoDB permissions to task role
cat > dynamodb-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/scotus_queries*",
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/scotus_responses*",
        "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/scotus_job_progress*"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name ${APP_NAME}-task-role \
  --policy-name DynamoDBAccess \
  --policy-document file://dynamodb-policy.json

# Get default VPC and subnets
echo "🌐 Getting VPC information..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text --region ${REGION})
SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=${VPC_ID}" --query 'Subnets[*].SubnetId' --output text --region ${REGION})
SUBNET_1=$(echo ${SUBNET_IDS} | cut -d' ' -f1)
SUBNET_2=$(echo ${SUBNET_IDS} | cut -d' ' -f2)

# Create security group
echo "🔒 Creating security group..."
SG_ID=$(aws ec2 create-security-group \
  --group-name ${APP_NAME}-sg \
  --description "Security group for ${APP_NAME}" \
  --vpc-id ${VPC_ID} \
  --region ${REGION} \
  --query 'GroupId' --output text 2>/dev/null || \
  aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=${APP_NAME}-sg" \
    --query 'SecurityGroups[0].GroupId' --output text --region ${REGION})

# Allow inbound traffic on port 5000
aws ec2 authorize-security-group-ingress \
  --group-id ${SG_ID} \
  --protocol tcp \
  --port 5000 \
  --cidr 0.0.0.0/0 \
  --region ${REGION} 2>/dev/null || echo "Security group rule already exists"

# Allow inbound traffic on port 80 for load balancer
aws ec2 authorize-security-group-ingress \
  --group-id ${SG_ID} \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0 \
  --region ${REGION} 2>/dev/null || echo "Port 80 security group rule already exists"

# Create task definition
echo "📋 Creating ECS task definition..."
cat > task-definition.json << EOF
{
  "family": "${APP_NAME}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${APP_NAME}-execution-role",
  "taskRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${APP_NAME}-task-role",
  "containerDefinitions": [
    {
      "name": "${APP_NAME}",
      "image": "${ECR_REPO}:latest",
      "portMappings": [
        {
          "containerPort": 5000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "PORT",
          "value": "5000"
        }
      ],
      "secrets": [
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:ssm:${REGION}:${ACCOUNT_ID}:parameter/${APP_NAME}/openai-api-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${APP_NAME}",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF

# Create CloudWatch log group
echo "📊 Creating CloudWatch log group..."
aws logs create-log-group --log-group-name /ecs/${APP_NAME} --region ${REGION} 2>/dev/null || echo "Log group already exists"

# Store OpenAI API key in Parameter Store
echo "🔐 Storing OpenAI API key in Parameter Store..."
if [ -f .env ]; then
  OPENAI_KEY=$(grep OPENAI_API_KEY .env | cut -d'=' -f2 | tr -d "'\"")
  aws ssm put-parameter \
    --name "/${APP_NAME}/openai-api-key" \
    --value "${OPENAI_KEY}" \
    --type "SecureString" \
    --region ${REGION} \
    --overwrite 2>/dev/null || echo "Parameter already exists"
else
  echo "⚠️ No .env file found. Please set OPENAI_API_KEY manually in Parameter Store:"
  echo "aws ssm put-parameter --name '/${APP_NAME}/openai-api-key' --value 'your-key-here' --type 'SecureString' --region ${REGION}"
fi

# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json --region ${REGION}

# Create ECS service
echo "🚀 Creating ECS service..."
aws ecs create-service \
  --cluster ${APP_NAME}-cluster \
  --service-name ${APP_NAME}-service \
  --task-definition ${APP_NAME} \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_1},${SUBNET_2}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}" \
  --enable-execute-command \
  --region ${REGION} 2>/dev/null || echo "Service already exists, updating..."

# Update service if it already exists
aws ecs update-service \
  --cluster ${APP_NAME}-cluster \
  --service ${APP_NAME}-service \
  --task-definition ${APP_NAME} \
  --region ${REGION} 2>/dev/null

# Create Application Load Balancer
echo "⚖️ Creating Application Load Balancer..."
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name ${APP_NAME}-alb \
  --subnets ${SUBNET_1} ${SUBNET_2} \
  --security-groups ${SG_ID} \
  --region ${REGION} \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text 2>/dev/null || \
  aws elbv2 describe-load-balancers \
    --names ${APP_NAME}-alb \
    --query 'LoadBalancers[0].LoadBalancerArn' --output text --region ${REGION})

# Create target group
echo "🎯 Creating target group..."
TG_ARN=$(aws elbv2 create-target-group \
  --name ${APP_NAME}-tg \
  --protocol HTTP \
  --port 5000 \
  --vpc-id ${VPC_ID} \
  --target-type ip \
  --health-check-path /health \
  --region ${REGION} \
  --query 'TargetGroups[0].TargetGroupArn' --output text 2>/dev/null || \
  aws elbv2 describe-target-groups \
    --names ${APP_NAME}-tg \
    --query 'TargetGroups[0].TargetGroupArn' --output text --region ${REGION})

# Create listener
echo "👂 Creating ALB listener..."
aws elbv2 create-listener \
  --load-balancer-arn ${ALB_ARN} \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=${TG_ARN} \
  --region ${REGION} 2>/dev/null || echo "Listener already exists"

# Update ECS service to use load balancer
echo "🔗 Updating ECS service with load balancer..."
aws ecs update-service \
  --cluster ${APP_NAME}-cluster \
  --service ${APP_NAME}-service \
  --load-balancers targetGroupArn=${TG_ARN},containerName=${APP_NAME},containerPort=5000 \
  --region ${REGION}

# Create API Gateway
echo "🌐 Creating API Gateway..."
API_ID=$(aws apigatewayv2 create-api \
  --name ${APP_NAME}-api \
  --protocol-type HTTP \
  --target "http://$(aws elbv2 describe-load-balancers --load-balancer-arns ${ALB_ARN} --query 'LoadBalancers[0].DNSName' --output text --region ${REGION})" \
  --region ${REGION} \
  --query 'ApiId' --output text 2>/dev/null || \
  aws apigatewayv2 get-apis \
    --query "Items[?Name=='${APP_NAME}-api'].ApiId" --output text --region ${REGION})

# Get API Gateway endpoint
API_ENDPOINT=$(aws apigatewayv2 get-api --api-id ${API_ID} --query 'ApiEndpoint' --output text --region ${REGION})

# Clean up temporary files
rm -f task-execution-role-trust-policy.json task-role-trust-policy.json task-definition.json parameter-store-policy.json documentdb-policy.json dynamodb-policy.json

echo "✅ Deployment complete!"
echo ""
echo "🌐 Your application is accessible at:"
echo "   API Gateway: ${API_ENDPOINT}"
echo "   Load Balancer: http://$(aws elbv2 describe-load-balancers --load-balancer-arns ${ALB_ARN} --query 'LoadBalancers[0].DNSName' --output text --region ${REGION})"
echo ""
echo "📊 Monitor your deployment:"
echo "   ECS Console: https://console.aws.amazon.com/ecs/home?region=${REGION}#/clusters/${APP_NAME}-cluster"
echo "   CloudWatch Logs: https://console.aws.amazon.com/cloudwatch/home?region=${REGION}#logsV2:log-groups/log-group/%2Fecs%2F${APP_NAME}"
echo ""
echo "🔧 Useful commands:"
echo "   Check service status: aws ecs describe-services --cluster ${APP_NAME}-cluster --services ${APP_NAME}-service --region ${REGION}"
echo "   View logs: aws logs tail /ecs/${APP_NAME} --follow --region ${REGION}"
