#!/bin/bash

# Build and Deploy MCP Server Only
# Usage: ./build_mcp_server.sh <environment> <aws-region>

set -e

ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-ap-southeast-2}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Building and deploying MCP Server for environment: $ENVIRONMENT in region: $AWS_REGION"

# Get ECR repository URL from Terraform
cd ../infra/2-chatbot-interface
MCP_SERVER_REPO=$(terraform output -raw ecr_mcp_server_url 2>/dev/null || echo "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/data-platform-mcp-${ENVIRONMENT}-mcp-server")

echo "MCP Server Repository: $MCP_SERVER_REPO"

# Login to ECR
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push MCP Server
echo "Building MCP Server container..."
cd ../../src/mcp_server
docker buildx build --platform linux/amd64 -t $MCP_SERVER_REPO:latest --push .

# Update ECS service
echo "Updating MCP Server ECS service..."
aws ecs update-service \
    --cluster "data-platform-mcp-${ENVIRONMENT}-cluster" \
    --service "data-platform-mcp-${ENVIRONMENT}-mcp-server" \
    --force-new-deployment \
    --region $AWS_REGION \
    --no-cli-pager \
    --output text > /dev/null

echo "MCP Server deployment complete!"
echo "Check service status with:"
echo "aws ecs describe-services --cluster data-platform-mcp-${ENVIRONMENT}-cluster --services data-platform-mcp-${ENVIRONMENT}-mcp-server --region $AWS_REGION"