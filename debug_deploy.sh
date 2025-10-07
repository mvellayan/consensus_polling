#!/bin/bash

APP_NAME="ai-supreme-court"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}"

echo "🐛 Deploying debug version..."

# Login and build minimal image
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_REPO}
docker build -f Dockerfile.debug -t ${APP_NAME}-debug .
docker tag ${APP_NAME}-debug:latest ${ECR_REPO}:debug
docker push ${ECR_REPO}:debug

# Update task definition to use debug image
cat > task-definition-debug.json << EOF
{
  "family": "${APP_NAME}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${APP_NAME}-execution-role",
  "taskRoleArn": "arn:aws:iam::${ACCOUNT_ID}:role/${APP_NAME}-task-role",
  "containerDefinitions": [
    {
      "name": "${APP_NAME}",
      "image": "${ECR_REPO}:debug",
      "portMappings": [{"containerPort": 5000, "protocol": "tcp"}],
      "environment": [{"name": "PORT", "value": "5000"}],
      "secrets": [{"name": "OPENAI_API_KEY", "valueFrom": "arn:aws:ssm:${REGION}:${ACCOUNT_ID}:parameter/${APP_NAME}/openai-api-key"}],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${APP_NAME}",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "debug"
        }
      }
    }
  ]
}
EOF

aws ecs register-task-definition --cli-input-json file://task-definition-debug.json --region ${REGION}
aws ecs update-service --cluster ${APP_NAME}-cluster --service ${APP_NAME}-service --task-definition ${APP_NAME} --region ${REGION}

rm task-definition-debug.json

echo "✅ Debug version deployed. Check logs:"
echo "aws logs tail /ecs/${APP_NAME} --follow --region ${REGION}"
