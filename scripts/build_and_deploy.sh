#!/bin/bash

# Build and Deploy Script for Containerized MCP Server
# Usage: ./build_and_deploy.sh <environment> <aws-region>

set -e

ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-ap-southeast-2}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Building and deploying for environment: $ENVIRONMENT in region: $AWS_REGION"

# Get ECR repository URLs from Terraform
cd ../infra/2-chatbot-interface
MCP_SERVER_REPO=$(terraform output -raw ecr_mcp_server_url 2>/dev/null || echo "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/remote-mcp-server-${ENVIRONMENT}-mcp-server")
GRADIO_UI_REPO=$(terraform output -raw ecr_repository_url 2>/dev/null || echo "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/remote-mcp-server-${ENVIRONMENT}-gradio-ui")

echo "MCP Server Repository: $MCP_SERVER_REPO"
echo "Gradio UI Repository: $GRADIO_UI_REPO"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push MCP Server
echo "Building MCP Server container..."
cd ../../src/mcp_server
docker buildx build --platform linux/amd64 -t $MCP_SERVER_REPO:latest --push .

# Build and push Gradio UI
echo "Building Gradio UI container..."
cd ../gradio_ui
docker buildx build --platform linux/amd64 -t $GRADIO_UI_REPO:latest --push .

# Update ECS services
echo "Updating ECS services..."
aws ecs update-service \
    --cluster "remote-mcp-server-${ENVIRONMENT}-cluster" \
    --service "remote-mcp-server-${ENVIRONMENT}-mcp-server" \
    --force-new-deployment \
    --region $AWS_REGION

aws ecs update-service \
    --cluster "remote-mcp-server-${ENVIRONMENT}-cluster" \
    --service "remote-mcp-server-${ENVIRONMENT}-gradio-ui" \
    --force-new-deployment \
    --region $AWS_REGION

echo "Deployment complete!"
echo "Check service status with:"
echo "aws ecs describe-services --cluster remote-mcp-server-${ENVIRONMENT}-cluster --services remote-mcp-server-${ENVIRONMENT}-mcp-server remote-mcp-server-${ENVIRONMENT}-gradio-ui --region $AWS_REGION"