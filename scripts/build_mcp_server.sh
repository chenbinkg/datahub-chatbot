#!/bin/bash

# Build and Deploy MCP Server to ECS
# Usage: ./build_mcp_server.sh <environment> <aws-region> [ecr-repo-url] [cluster-name] [service-name] [image-tag]

set -e

ENVIRONMENT=${1:-dev}
AWS_REGION=${2:-ap-southeast-2}
ECR_REPO_OVERRIDE=${3:-}
CLUSTER_OVERRIDE=${4:-}
SERVICE_OVERRIDE=${5:-}
IMAGE_TAG=${6:-latest}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Building and deploying MCP Server for environment: $ENVIRONMENT in region: $AWS_REGION"

# Get ECR repository URL from Terraform
cd ../infra/2-chatbot-interface
if [ -n "$ECR_REPO_OVERRIDE" ]; then
    MCP_SERVER_REPO="$ECR_REPO_OVERRIDE"
else
    MCP_SERVER_REPO=$(terraform output -raw ecr_mcp_server_url 2>/dev/null || echo "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/datahub-mcp-${ENVIRONMENT}-mcp-server")
fi

echo "MCP Server Repository: $MCP_SERVER_REPO"

# Login to ECR (use account registry domain)
echo "Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Ensure docker buildx is available
echo "Ensuring docker buildx is available..."
docker buildx version >/dev/null 2>&1 || docker buildx create --use

# Build and push MCP Server
echo "Building and pushing MCP Server container (buildx) with tag: $IMAGE_TAG..."
cd ../../src/mcp_servers
docker buildx build --platform linux/amd64 -t $MCP_SERVER_REPO:$IMAGE_TAG --push .

# Determine cluster and service (allow overrides)
CLUSTER_NAME=${CLUSTER_OVERRIDE:-datahub-mcp-${ENVIRONMENT}-cluster}
SERVICE_NAME=${SERVICE_OVERRIDE:-datahub-mcp-${ENVIRONMENT}-mcp-server}

echo "Updating MCP Server ECS service $SERVICE_NAME on cluster $CLUSTER_NAME..."
aws ecs update-service \
    --cluster "$CLUSTER_NAME" \
    --service "$SERVICE_NAME" \
    --force-new-deployment \
    --region $AWS_REGION \
    --no-cli-pager \
    --output text > /dev/null

echo "MCP Server deployment complete!"
echo "Check service status with:"
echo "aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --region $AWS_REGION"