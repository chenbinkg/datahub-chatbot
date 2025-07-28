# Deployment Guide - Containerized Approach

## Prerequisites

1. AWS CLI configured with appropriate permissions
2. Terraform installed (version 1.0.0 or later)
3. Docker installed (for building container images)

## Step 1: Deploy Infrastructure

1. Navigate to the infrastructure directory and initialize Terraform with S3 backend:
```bash
cd infra/2-chatbot-interface
export PROJECT_CODE=FPEI2606
export PROJECT_NAME=data-platform-mcp
export ENVIRONMENT=dev
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
terraform init -backend-config="bucket=${PROJECT_NAME}-${ENVIRONMENT}-${AWS_ACCOUNT_ID}-terraform-state" -backend-config="key=${PROJECT_CODE}/${PROJECT_NAME}/${ENVIRONMENT}.tfstate"
```

2. Review the deployment plan:
```bash
terraform plan -out=plan.tfplan \
  -var="environment=${ENVIRONMENT}" \
  -var="mongo_uri=mongodb+srv://username:password@cluster.mongodb.net" \
  -var="mongo_db=data_platform"
```

3. Deploy the infrastructure:
```bash
terraform apply plan.tfplan
```

**Note**: The infrastructure creates:
- ECS Fargate cluster and services
- ECR repositories for containers
- Cognito User Pool and Client
- Bedrock Agent and Alias
- All necessary networking and IAM roles

## Step 3: Build and Deploy Containers

### Option A: Using the Build Script (Recommended)

```bash
cd ../../scripts
chmod +x build_and_deploy.sh
./build_and_deploy.sh dev ap-southeast-2
```

### Option B: Manual Build and Deploy

1. Get ECR repository URLs:
```bash
cd infra/2-chatbot-interface
terraform output ecr_mcp_server_url
terraform output ecr_repository_url
```

2. Login to ECR:
```bash
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-southeast-2.amazonaws.com
```

3. Build and push MCP Server:
```bash
cd ../../src/mcp_server
docker buildx build --platform linux/amd64 -t <mcp-server-repo-url>:latest --push .
```

4. Build and push Gradio UI:
```bash
cd ../gradio_ui
docker buildx build --platform linux/amd64 -t <gradio-ui-repo-url>:latest --push .
```

5. Update ECS services:
```bash
aws ecs update-service --cluster <cluster-name> --service <mcp-service-name> --force-new-deployment --region ap-southeast-2
aws ecs update-service --cluster <cluster-name> --service <gradio-service-name> --force-new-deployment --region ap-southeast-2
```

## Step 4: Access the Application

1. Get the ALB DNS name:
```bash
terraform output alb_dns_name
```

2. Access the Gradio UI at: `http://<alb-dns-name>`

## Local Development

1. Start local development environment:
```bash
cd src/mcp_server
docker-compose up
```

2. Access locally:
- MCP Server: `http://localhost:8000`
- MongoDB MCP Server: `http://localhost:8001`
- Local MongoDB: `mongodb://admin:password@localhost:27017`

## Troubleshooting

1. **Check ECS service status**:
```bash
aws ecs describe-services --cluster <cluster-name> --services <service-name> --region ap-southeast-2
```

2. **Check container logs**:
```bash
aws logs describe-log-groups --log-group-name-prefix "/ecs/" --region ap-southeast-2
aws logs tail /ecs/<service-name> --follow --region ap-southeast-2
```

3. **Local testing**:
```bash
cd src/mcp_server
docker-compose up
curl http://localhost:8000/health
```