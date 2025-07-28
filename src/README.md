# Data Platform Chatbot Interface

This project implements a Gradio-based chatbot interface that connects to a MongoDB database through a remote MCP (Model Context Protocol) server hosted on AWS.

## Components

### 1. Gradio UI

The Gradio UI provides a web interface for users to interact with the chatbot. It includes:

- Authentication via AWS Cognito
- Chat interface for querying the database
- Integration with AWS Bedrock for AI capabilities

### 2. MCP Server

The MCP server processes requests from the Gradio UI and interacts with the MongoDB database. It includes:

- MongoDB MCP: Our custom implementation for database operations
- External MongoDB MCP: Integration with the official [MongoDB MCP server](https://github.com/mongodb-js/mongodb-mcp-server)
- AWS MCP: For AWS service interactions
- Sequential Thinking MCP: For complex reasoning tasks

## Infrastructure

The infrastructure is managed using Terraform and includes:

- VPC with public and private subnets
- EC2 instance for hosting the MCP server
- ECS cluster for the Gradio UI container
- Application Load Balancer for traffic distribution
- Cognito User Pool for authentication

## Deployment

### Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform installed
- Docker installed (for building and pushing container images)

### Deployment Steps

1. Deploy the infrastructure:

```bash
cd infra/2-chatbot-interface
export PROJECT_CODE=FPEI2606
export PROJECT_NAME=data-platform-remote-mcp-server
export ENVIRONMENT=dev
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
terraform init -backend-config="bucket=${PROJECT_NAME}-${ENVIRONMENT}-${AWS_ACCOUNT_ID}-terraform-state" -backend-config="key=${PROJECT_CODE}/${PROJECT_NAME}/${ENVIRONMENT}.tfstate"
terraform plan -var="environment=${ENVIRONMENT}" -var="mongo_uri=your-mongodb-uri" -var="mongo_db=data_platform"
terraform apply -var="environment=${ENVIRONMENT}" -var="mongo_uri=your-mongodb-uri" -var="mongo_db=data_platform"
```

2. Build and push the Gradio UI container:

```bash
cd src/gradio_ui
aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com
docker build -t <ecr-repo-url>:latest .
docker push <ecr-repo-url>:latest
```

3. Update the ECS service to deploy the new container:

```bash
aws ecs update-service --cluster <cluster-name> --service <service-name> --force-new-deployment
```

## Usage

1. Access the Gradio UI through the ALB URL
2. Log in using Cognito credentials
3. Start chatting with the interface to query the MongoDB database

## Adding New MCP Servers

To add a new MCP server:

1. Create a new MCP class in `src/mcp_server/mcp/`
2. Update the main.py file to include the new MCP
3. Deploy the updated code to the EC2 instance

## Cross-Region Bedrock Inference

This infrastructure supports cross-region inference with AWS Bedrock models. The IAM policies are configured to allow access to Bedrock services in any region. This is necessary because certain models like Claude are only available in specific regions (e.g., us-east-1).

When using the Sequential Thinking MCP, you can specify the region in the parameters:

```json
{
  "query": "Your query here",
  "mcp_type": "sequential_thinking",
  "parameters": {
    "model_id": "anthropic.claude-sonnet-4-20250514-v1:0",
    "region": "us-east-1"
  }
}
```