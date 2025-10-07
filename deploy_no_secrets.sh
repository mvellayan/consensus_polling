#!/bin/bash

APP_NAME="ai-supreme-court"
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}"

echo "🚀 Deploying without secrets for testing..."

# Build with explicit platform
docker buildx build --platform linux/amd64 -t ${APP_NAME}-test . --load
docker tag ${APP_NAME}-test:latest ${ECR_REPO}:test

# Login and push
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_REPO}
docker push ${ECR_REPO}:test

# Create task definition without secrets
cat > task-definition-no-secrets.json << EOF
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
      "image": "${ECR_REPO}:test",
      "portMappings": [{"containerPort": 5000, "protocol": "tcp"}],
      "environment": [
        {"name": "PORT", "value": "5000"},
        {"name": "OPENAI_API_KEY", "value": "test-key-for-debugging"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${APP_NAME}",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "test"
        }
      }
    }
  ]
}
EOF

# Register and update
aws ecs register-task-definition --cli-input-json file://task-definition-no-secrets.json --region ${REGION}
aws ecs update-service --cluster ${APP_NAME}-cluster --service ${APP_NAME}-service --task-definition ${APP_NAME} --region ${REGION}

rm task-definition-no-secrets.json

echo "✅ Test deployment without secrets complete!"
