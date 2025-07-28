#!/bin/bash

# Build and deploy Gradio UI container to ECR
# Usage: ./deploy_gradio_ui.sh <aws-region> <ecr-repo-url>

AWS_REGION=$1
ECR_REPO_URL=$2

if [ -z "$AWS_REGION" ] || [ -z "$ECR_REPO_URL" ]; then
    echo "Usage: ./deploy_gradio_ui.sh <aws-region> <ecr-repo-url>"
    exit 1
fi

echo "Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REPO_URL"

echo "Building Gradio UI container..."
cd "$(dirname "$0")/../src/gradio_ui"
docker build -t "$ECR_REPO_URL:latest" .

echo "Pushing container to ECR..."
docker push "$ECR_REPO_URL:latest"

echo "Updating ECS service..."
CLUSTER_NAME=$(aws ecs list-clusters --region "$AWS_REGION" --query "clusterArns[?contains(@, 'gradio')]" --output text | awk -F'/' '{print $2}')
SERVICE_NAME=$(aws ecs list-services --cluster "$CLUSTER_NAME" --region "$AWS_REGION" --query "serviceArns[0]" --output text | awk -F'/' '{print $3}')

aws ecs update-service --cluster "$CLUSTER_NAME" --service "$SERVICE_NAME" --force-new-deployment --region "$AWS_REGION"

echo "Deployment complete!"