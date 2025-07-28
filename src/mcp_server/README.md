# MCP Server

This is the containerized MCP (Model Context Protocol) server for the Data Platform project.

## Architecture

The MCP server runs as a single Docker container that includes:
- **Custom MCP Server** (Port 8000): FastAPI application with multiple MCP implementations
- **External MongoDB MCP Server** (Port 8001): Official MongoDB MCP server from GitHub
- **Multiple MCP Types**: MongoDB, AWS, Sequential Thinking MCPs

## Configuration

The MCP server uses AWS Systems Manager Parameter Store for configuration. All parameters are automatically created by Terraform during infrastructure deployment.

## Deployment

### Prerequisites
- AWS CLI configured with appropriate permissions
- Terraform installed (version 1.0.0 or later)
- Docker installed (for building container images)

### Step 1: Deploy Infrastructure

Deploy the infrastructure using Terraform (this automatically creates all SSM parameters):

```bash
cd ../../infra/2-chatbot-interface
export PROJECT_CODE=FPEI2606
export PROJECT_NAME=data-platform-remote-mcp-server
export ENVIRONMENT=dev
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Initialize Terraform with S3 backend
terraform init -backend-config="bucket=${PROJECT_NAME}-${ENVIRONMENT}-${AWS_ACCOUNT_ID}-terraform-state" -backend-config="key=${PROJECT_CODE}/${PROJECT_NAME}/${ENVIRONMENT}.tfstate"

# Review and apply infrastructure
terraform plan -out=plan.tfplan -var="environment=${ENVIRONMENT}" -var="mongo_uri=mongodb+srv://username:password@cluster.mongodb.net" -var="mongo_db=data_platform"
terraform apply plan.tfplan
```

### Step 2: Build and Deploy Container

Build and deploy the MCP server container:

```bash
cd ../../scripts
chmod +x build_and_deploy.sh
./build_and_deploy.sh dev ap-southeast-2
```

### Step 3: Verify Deployment

Check the deployment status:

```bash
# Get ALB DNS name
terraform output alb_dns_name

# Check ECS service status
aws ecs describe-services --cluster remote-mcp-server-dev-cluster --services remote-mcp-server-dev-mcp-server --region ap-southeast-2
```

## Local Development

For local development, use Docker Compose:

```bash
# Start local development environment
docker-compose up

# Access services locally
# MCP Server: http://localhost:8000
# MongoDB MCP Server: http://localhost:8001
# Local MongoDB: mongodb://admin:password@localhost:27017
```

### Local Testing

```bash
# Test MCP server health
curl http://localhost:8000/health

# Test MCP processing
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "mcp_type": "mongodb"}'
```

## Configuration Parameters

The following SSM parameters are automatically created by Terraform:

- `/remote-mcp-server/aws-region`: AWS region
- `/remote-mcp-server/mongo-uri`: MongoDB connection URI (from terraform variable)
- `/remote-mcp-server/mongo-db`: MongoDB database name (from terraform variable)
- `/remote-mcp-server/mcp-server-url`: Internal MCP server URL
- `/remote-mcp-server/mongodb-mcp-server-url`: Internal MongoDB MCP server URL
- `/remote-mcp-server/cognito-user-pool-id`: Cognito User Pool ID
- `/remote-mcp-server/cognito-client-id`: Cognito Client ID
- `/remote-mcp-server/bedrock-agent-id`: Bedrock Agent ID
- `/remote-mcp-server/bedrock-agent-alias-id`: Bedrock Agent Alias ID

## Container Features

- **Single Container**: Both MCP servers run in one container for simplicity
- **Multi-Port**: Exposes ports 8000 and 8001
- **Auto-Scaling**: ECS Fargate handles scaling based on demand
- **Centralized Logging**: All logs go to CloudWatch under `/ecs/` log groups
- **Cross-Region AI**: Supports Bedrock models in different regions

## Troubleshooting

```bash
# Check container logs
aws logs tail /ecs/remote-mcp-server-dev-mcp-server --follow --region ap-southeast-2

# Check ECS service events
aws ecs describe-services --cluster remote-mcp-server-dev-cluster --services remote-mcp-server-dev-mcp-server --region ap-southeast-2

# Verify SSM parameters
aws ssm get-parameters-by-path --path "/remote-mcp-server" --region ap-southeast-2
```