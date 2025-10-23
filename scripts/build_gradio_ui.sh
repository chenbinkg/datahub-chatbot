#!/bin/bash

# Build and Deploy Unified App Only
# Usage: ./build_gradio_ui.sh <environment> <aws-region>

set -e

ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-ap-southeast-2}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Building and deploying unified app for environment: $ENVIRONMENT in region: $AWS_REGION"

# Get ECR repository URL from Terraform
cd ../infra/2-chatbot-interface
UNIFIED_APP_REPO=$(terraform output -raw ecr_repository_url 2>/dev/null || echo "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/datahub-mcp-${ENVIRONMENT}-gradio-ui")

echo "Unified App Repository: $UNIFIED_APP_REPO"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push unified app
echo "Building unified app container..."
cd ../../src/unified_app
docker buildx build --platform linux/amd64 -t $UNIFIED_APP_REPO:latest --push .

# Update ECS service
echo "Updating unified app ECS service..."
aws ecs update-service \
    --cluster "datahub-mcp-${ENVIRONMENT}-cluster" \
    --service "datahub-mcp-${ENVIRONMENT}-gradio-ui" \
    --force-new-deployment \
    --region $AWS_REGION \
    --no-cli-pager \
    --output text > /dev/null

echo "Unified app deployment complete!"
echo "Check service status with:"
echo "aws ecs describe-services --cluster datahub-mcp-${ENVIRONMENT}-cluster --services datahub-mcp-${ENVIRONMENT}-gradio-ui --region $AWS_REGION"