# Chatbot Interface Infrastructure

This directory contains the Terraform code for deploying the Gradio chatbot interface infrastructure on AWS.

## Architecture

The infrastructure consists of the following components:

- **VPC**: A Virtual Private Cloud with public and private subnets across multiple availability zones
- **EC2**: An EC2 instance running the MCP server (both custom and MongoDB MCP server)
- **ECS**: A Fargate cluster running the Gradio UI container
- **ALB**: An Application Load Balancer for distributing traffic to the Gradio UI
- **Cognito**: A User Pool for authentication
- **IAM**: Roles and policies for EC2 and ECS
- **ECR**: A repository for the Gradio UI container image

## File Structure

- `main.tf`: Provider configuration and locals
- `variables.tf`: Input variables
- `outputs.tf`: Output values
- `networking.tf`: VPC and security groups
- `ec2.tf`: EC2 instance for MCP server
- `ecs.tf`: ECS cluster, task definition, and service
- `alb.tf`: Application Load Balancer
- `cognito.tf`: Cognito User Pool
- `iam.tf`: IAM roles and policies

## Usage

### Prerequisites

- Terraform 1.0.0 or later
- AWS CLI configured with appropriate permissions
- SSH key pair for EC2 instance

### Deployment

1. Initialize Terraform with S3 backend:

```bash
cd infra/2-chatbot-interface
export PROJECT_CODE=FPEI2606
export PROJECT_NAME=data-platform-mcp
export ENVIRONMENT=dev
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
terraform init -backend-config="bucket=${PROJECT_NAME}-${ENVIRONMENT}-${AWS_ACCOUNT_ID}-terraform-state" -backend-config="key=${PROJECT_CODE}/${PROJECT_NAME}/${ENVIRONMENT}.tfstate"
```

2. Review the plan:

```bash
terraform plan -out=plan.tfplan -var="environment=${ENVIRONMENT}" -var="mongo_uri=your-mongodb-uri" -var="mongo_db=data_platform"
```

3. Apply the changes:

```bash
terraform apply plan.tfplan
```

### Environment Variables

The infrastructure supports different environments (dev, test, prod) by appending the environment name to resource names. This allows you to deploy multiple environments without conflicts.

Example:

```bash
terraform plan -var="environment=dev"
terraform plan -var="environment=test"
terraform plan -var="environment=prod"
```

## MongoDB Integration

This infrastructure is designed to work with MongoDB databases in the ap-southeast-2 region to minimize cross-region data transfer costs. The MCP server includes both a custom implementation and the official MongoDB MCP server from GitHub.

## Cross-Region Bedrock Inference

The infrastructure includes IAM policies that allow cross-region access to AWS Bedrock services. This is necessary because some Bedrock models (like Claude) are only available in specific regions (e.g., us-east-1) while your infrastructure is deployed in ap-southeast-2.

The MCP server code is designed to handle cross-region model inference by creating region-specific Bedrock clients as needed.

## Bedrock Agent

This infrastructure includes a Terraform-managed AWS Bedrock agent that can interact with the MCP server. The agent is created with:

- A Lambda function that forwards requests to the MCP server
- An action group with an OpenAPI schema for the MCP API
- An agent alias for deployment
- Appropriate IAM roles and policies

The agent ID and alias ID are automatically stored in SSM Parameter Store for use by the application. This approach follows Infrastructure as Code (IaC) best practices by managing the Bedrock agent through Terraform rather than manual console configuration.

## Configuration Management

This infrastructure uses AWS Systems Manager Parameter Store for configuration management. All configuration parameters are stored in SSM under the `/remote-mcp-server/` prefix. This approach provides several benefits:

1. Secure storage of sensitive information like database credentials
2. Centralized configuration management
3. No need to rebuild containers when configuration changes
4. Easy integration with AWS services

The following parameters are managed by Terraform:

- `/remote-mcp-server/aws-region`
- `/remote-mcp-server/mcp-server-url`
- `/remote-mcp-server/mongodb-mcp-server-url`
- `/remote-mcp-server/cognito-user-pool-id`
- `/remote-mcp-server/cognito-client-id`
- `/remote-mcp-server/mongo-uri`
- `/remote-mcp-server/mongo-db`
- `/remote-mcp-server/bedrock-agent-id`
- `/remote-mcp-server/bedrock-agent-alias-id`

You can set these parameters when planning the Terraform configuration:

```bash
terraform plan -var="mongo_uri=mongodb://username:password@hostname:27017" -var="bedrock_agent_id=your-agent-id"

## Outputs

After deployment, Terraform will output:

- ALB DNS name for accessing the Gradio UI
- Cognito User Pool ID and Client ID
- MCP server private IP address
- ECR repository URL for the Gradio UI container
- VPC ID and subnet IDs