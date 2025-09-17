# CI/CD Pipeline Deployment Guide

## Overview

This CI/CD pipeline automates the complete deployment of the Remote MCP Server project, including:

- **Infrastructure**: Terraform-managed AWS resources (VPC, ECS, Lambda, Bedrock, etc.)
- **Lambda Functions**: MCP Agent and Neptune Proxy functions
- **Containers**: MCP Server and Gradio UI (deployed to ECS Fargate)
- **Security**: Checkov infrastructure scanning and ShellCheck for scripts

## Pipeline Architecture

### 1. Quality & Security Checks
- **Checkov**: Infrastructure security scanning
- **ShellCheck**: Shell script linting

### 2. Lambda Functions
- **Package**: Creates deployment packages for both Lambda functions
- **Deploy**: Deployed via Terraform infrastructure

### 3. Infrastructure Deployment
- **Terraform Init**: Sets up S3 backend for state management
- **Terraform Deploy**: Deploys complete AWS infrastructure

### 4. Container Deployment
- **Build**: Builds Docker images for MCP Server and Gradio UI
- **Push**: Pushes images to ECR repositories
- **Deploy**: Updates ECS services with new images

### 5. Health Checks
- **ALB Health**: Validates application load balancer response
- **Service Status**: Confirms ECS services are running

## Required GitHub Secrets

Configure these secrets in your GitHub repository:

```
AWS_ACCESS_KEY_ID       # AWS access key for deployment
AWS_SECRET_ACCESS_KEY   # AWS secret key for deployment
MONGO_URI              # MongoDB connection string
MONGO_DB               # MongoDB database name
```

## Deployment Components

### Terraform Infrastructure (2-stage)

**Stage 1: Backend Setup** (`infra/1-terraform-init/`)
- S3 bucket for Terraform state
- DynamoDB table for state locking

**Stage 2: Main Infrastructure** (`infra/2-chatbot-interface/`)
- VPC with public/private subnets
- ECS Fargate cluster and services
- Application Load Balancer
- ECR repositories
- Lambda functions (MCP Agent, Neptune Proxy)
- Bedrock Agent with Knowledge Base
- Cognito User Pool for authentication
- IAM roles and policies
- SSM parameters for configuration

### Lambda Functions

**MCP Agent** (`lambda/lambda_functions/mcp_agent/`)
- Handles Bedrock Agent requests
- Routes queries to MCP server
- Supports multiple MCP types (mongodb, aws, sequential_thinking)

**Neptune Proxy** (`lambda/lambda_functions/neptune_proxy/`)
- Manages Neptune Analytics graph operations
- Loads taxonomy data
- Executes graph queries

### Container Services

**MCP Server** (`src/mcp_server/`)
- Multi-protocol MCP server
- MongoDB MCP server integration
- Supports HTTP and WebSocket transports
- Runs on ECS Fargate (port 8000, 8001)

**Gradio UI** (`src/gradio_ui/`)
- Web interface for chatbot interaction
- Cognito authentication integration
- Bedrock Agent communication
- Runs on ECS Fargate (port 7860)

## Pipeline Triggers

### Main Branch (Production Deployment)
- **Push to main**: Full deployment pipeline
- Runs all stages: security → lambda → terraform → containers → health checks

### Pull Requests (Validation)
- **PR creation/update**: Quality checks only
- Runs: Checkov, ShellCheck, Lambda packaging
- No deployment to AWS

### Manual Deployment

You can also deploy manually using the existing scripts:

```bash
# Deploy infrastructure
cd infra/2-chatbot-interface
terraform init -backend-config="bucket=..." -backend-config="key=..."
terraform plan -var="environment=dev" -var="mongo_uri=..." -var="mongo_db=..."
terraform apply

# Deploy containers
./scripts/build_and_deploy.sh dev ap-southeast-2

# Or deploy individual services
./scripts/build_mcp_server.sh dev ap-southeast-2
./scripts/build_gradio_ui.sh dev ap-southeast-2
```

## Environment Configuration

The pipeline uses these environment variables:

```yaml
AWS_REGION: ap-southeast-2
ENVIRONMENT: dev
PROJECT_CODE: FPEI2606
PROJECT_NAME: data-platform-mcp
```

Resource naming follows the pattern: `{PROJECT_NAME}-{ENVIRONMENT}-{RESOURCE_TYPE}`

Examples:
- ECS Cluster: `data-platform-mcp-dev-cluster`
- ECR Repository: `data-platform-mcp-dev-mcp-server`
- S3 Bucket: `data-platform-mcp-dev-{ACCOUNT_ID}-terraform-state`

## Deployment Validation

The pipeline includes comprehensive validation:

1. **Infrastructure Security**: Checkov scans Terraform code
2. **Script Quality**: ShellCheck validates shell scripts
3. **Lambda Packaging**: Validates Python dependencies
4. **Container Builds**: Multi-platform Docker builds
5. **Service Health**: ECS service stability checks
6. **Application Health**: ALB endpoint validation

## Troubleshooting

### Common Issues

**Terraform State Lock**
```bash
# If state is locked, force unlock (use carefully)
terraform force-unlock <LOCK_ID>
```

**ECR Authentication**
```bash
# Manual ECR login
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin <account>.dkr.ecr.ap-southeast-2.amazonaws.com
```

**ECS Service Issues**
```bash
# Check service status
aws ecs describe-services --cluster data-platform-mcp-dev-cluster --services data-platform-mcp-dev-mcp-server

# View logs
aws logs tail /ecs/data-platform-mcp-dev-mcp-server --follow
```

### Pipeline Failures

**Security Scan Failures**: Review Checkov report artifacts
**Lambda Package Failures**: Check Python dependencies and virtual environment setup
**Terraform Failures**: Review plan output and AWS permissions
**Container Build Failures**: Check Dockerfile syntax and dependencies
**Health Check Failures**: Verify ALB configuration and target group health

## Monitoring and Logs

**CloudWatch Logs**:
- `/ecs/data-platform-mcp-dev-mcp-server`
- `/ecs/data-platform-mcp-dev-gradio-ui`
- `/aws/lambda/data-platform-mcp-dev-mcp-agent`
- `/aws/lambda/data-platform-mcp-dev-neptune-proxy`

**ECS Service Monitoring**:
```bash
# Service status
aws ecs describe-services --cluster data-platform-mcp-dev-cluster --services data-platform-mcp-dev-mcp-server data-platform-mcp-dev-gradio-ui

# Task status
aws ecs list-tasks --cluster data-platform-mcp-dev-cluster --service-name data-platform-mcp-dev-mcp-server
```

## Security Considerations

- All secrets stored in GitHub Secrets
- IAM roles follow least privilege principle
- ECR repositories are private
- VPC uses private subnets for ECS tasks
- ALB terminates SSL (configure certificate in Terraform)
- Cognito provides authentication for Gradio UI

## Cost Optimization

- ECS Fargate tasks scale to zero when not in use
- Lambda functions are pay-per-invocation
- Neptune Analytics is serverless
- S3 and ECR have lifecycle policies (configure in Terraform)

## Next Steps

1. **SSL Certificate**: Add ACM certificate to ALB for HTTPS
2. **Custom Domain**: Configure Route53 for custom domain
3. **Monitoring**: Add CloudWatch dashboards and alarms
4. **Backup**: Configure automated backups for stateful resources
5. **Multi-Environment**: Extend pipeline for staging/production environments