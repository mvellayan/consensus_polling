# AWS Fargate Deployment Guide

This guide explains how to deploy the AI Supreme Court Flask application to AWS Fargate with API Gateway.

## Prerequisites

1. **AWS CLI configured** with appropriate permissions
2. **Docker installed** and running
3. **AWS Account** with the following permissions:
   - ECS (Elastic Container Service)
   - ECR (Elastic Container Registry)
   - IAM (Identity and Access Management)
   - VPC/EC2 (for networking)
   - Application Load Balancer
   - API Gateway
   - CloudWatch Logs
   - Systems Manager Parameter Store

## Quick Deploy

```bash
./deploy_fargate.sh
```

## What the deployment script does:

1. **Creates ECR repository** for Docker images
2. **Builds and pushes** Docker image to ECR
3. **Creates ECS cluster** and task definition
4. **Sets up IAM roles** with proper permissions
5. **Creates security groups** and networking
6. **Deploys Fargate service** with auto-scaling
7. **Sets up Application Load Balancer** for high availability
8. **Creates API Gateway** for internet access
9. **Configures CloudWatch logging**
10. **Stores secrets** in Parameter Store

## Architecture

```
Internet → API Gateway → Application Load Balancer → ECS Fargate Tasks
                                                   ↓
                                              CloudWatch Logs
                                                   ↓
                                            Parameter Store (secrets)
```

## Configuration

The deployment uses these default settings:
- **Region**: us-east-1
- **CPU**: 256 units (0.25 vCPU)
- **Memory**: 512 MB
- **Port**: 5000
- **Desired Count**: 1 task

## Environment Variables

The application requires:
- `OPENAI_API_KEY`: Stored securely in AWS Parameter Store
- `PORT`: Set to 5000 (configurable)

## Accessing Your Application

After deployment, you'll get two URLs:
1. **API Gateway URL**: `https://xxxxxxxx.execute-api.us-east-1.amazonaws.com`
2. **Load Balancer URL**: `http://ai-supreme-court-alb-xxxxxxxxx.us-east-1.elb.amazonaws.com`

## Monitoring

- **ECS Console**: Monitor service health and tasks
- **CloudWatch Logs**: View application logs at `/ecs/ai-supreme-court`
- **API Gateway Console**: Monitor API usage and performance

## Scaling

To scale your application:

```bash
aws ecs update-service \
  --cluster ai-supreme-court-cluster \
  --service ai-supreme-court-service \
  --desired-count 3 \
  --region us-east-1
```

## Updating the Application

1. Make your code changes
2. Run the deployment script again: `./deploy_fargate.sh`
3. The script will build a new image and update the service

## Cleanup

To remove all AWS resources:

```bash
./cleanup_fargate.sh
```

## Troubleshooting

### Check service status:
```bash
aws ecs describe-services \
  --cluster ai-supreme-court-cluster \
  --services ai-supreme-court-service \
  --region us-east-1
```

### View logs:
```bash
aws logs tail /ecs/ai-supreme-court --follow --region us-east-1
```

### Check task health:
```bash
aws ecs list-tasks \
  --cluster ai-supreme-court-cluster \
  --service-name ai-supreme-court-service \
  --region us-east-1
```

## Security Features

- **IAM roles** with least privilege access
- **Security groups** restricting network access
- **Secrets management** via Parameter Store
- **VPC isolation** using default VPC
- **HTTPS** available through API Gateway

## Cost Optimization

- Uses **Fargate Spot** for cost savings (optional)
- **Auto-scaling** based on CPU/memory usage
- **CloudWatch** for monitoring and alerting
- **Application Load Balancer** for efficient traffic distribution

## Support

For issues with deployment:
1. Check CloudWatch logs for application errors
2. Verify IAM permissions
3. Ensure Docker is running locally
4. Check AWS CLI configuration
