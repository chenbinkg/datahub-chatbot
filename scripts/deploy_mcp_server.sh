#!/bin/bash

# Build and deploy MCP server container to ECR and trigger ECS service update
# Usage: ./deploy_mcp_server.sh <aws-region> <ecr-repo-url> [cluster-name] [service-name]

AWS_REGION=$1
ECR_REPO_URL=$2
CLUSTER_NAME=${3:-}
SERVICE_NAME=${4:-}

if [ -z "$AWS_REGION" ] || [ -z "$ECR_REPO_URL" ]; then
    echo "Usage: ./deploy_mcp_server.sh <aws-region> <ecr-repo-url> [cluster-name] [service-name]"
    exit 1
fi

echo "Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REPO_URL"

echo "Building and pushing MCP server container (buildx)..."
cd "$(dirname "$0")/../src/mcp_servers"
# Use buildx to build for linux/amd64 and push directly to ECR (recommended for ECS Fargate)
docker buildx build --platform linux/amd64 -t "$ECR_REPO_URL:latest" --push .

echo "Finding ECS cluster and service (if not provided)..."
if [ -z "$CLUSTER_NAME" ]; then
    CLUSTER_NAME=$(aws ecs list-clusters --region "$AWS_REGION" --query "clusterArns[?contains(@, 'remote-mcp') || contains(@, 'datahub') ]" --output text | awk -F'/' '{print $2}' | head -n1)
fi
if [ -z "$SERVICE_NAME" ]; then
    SERVICE_NAME=$(aws ecs list-services --cluster "$CLUSTER_NAME" --region "$AWS_REGION" --query "serviceArns[?contains(@, 'mcp') || contains(@, 'remote-mcp') ]" --output text | awk -F'/' '{print $3}' | head -n1)
fi

if [ -z "$CLUSTER_NAME" ] || [ -z "$SERVICE_NAME" ]; then
    echo "Unable to auto-detect ECS cluster/service. Please provide cluster and service names as 3rd and 4th arguments."
    exit 1
fi

echo "Updating ECS service $SERVICE_NAME on cluster $CLUSTER_NAME..."
aws ecs update-service --cluster "$CLUSTER_NAME" --service "$SERVICE_NAME" --force-new-deployment --region "$AWS_REGION"

echo "Deployment complete!"