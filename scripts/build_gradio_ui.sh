#!/bin/bash

# Build and Deploy Gradio UI Only
# Usage: ./build_gradio_ui.sh <environment> <aws-region>

set -e

ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-ap-southeast-2}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Building and deploying Gradio UI for environment: $ENVIRONMENT in region: $AWS_REGION"

# Get ECR repository URL from Terraform
cd ../infra/2-chatbot-interface
GRADIO_UI_REPO=$(terraform output -raw ecr_repository_url 2>/dev/null || echo "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/data-platform-mcp-${ENVIRONMENT}-gradio-ui")

echo "Gradio UI Repository: $GRADIO_UI_REPO"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push Gradio UI
echo "Building Gradio UI container..."
cd ../../src/gradio_ui
docker buildx build --platform linux/amd64 -t $GRADIO_UI_REPO:latest --push .

# Update ECS service
echo "Updating Gradio UI ECS service..."
aws ecs update-service \
    --cluster "data-platform-mcp-${ENVIRONMENT}-cluster" \
    --service "data-platform-mcp-${ENVIRONMENT}-gradio-ui" \
    --force-new-deployment \
    --region $AWS_REGION \
    --no-cli-pager \
    --output text > /dev/null

echo "Gradio UI deployment complete!"
echo "Check service status with:"
echo "aws ecs describe-services --cluster data-platform-mcp-${ENVIRONMENT}-cluster --services data-platform-mcp-${ENVIRONMENT}-gradio-ui --region $AWS_REGION"