# DataHub Chatbot

AI-powered chatbot for DataHub metadata search and dataset access using Strands Agent with cloud-based MCP servers.

## Features

- **Unified App**: Gradio UI with embedded Strands Agent and BedrockModel
- **Real-time Streaming**: Live response updates as text generates
- **Cloud-based MCP Servers**: HTTP-accessible MongoDB and S3 MCP servers on ECS
- **Official MongoDB MCP**: Using @mongodb-js/mongodb-mcp-server for database queries
- **S3 Presigned URLs**: Custom MCP server for secure dataset downloads
- **Comprehensive Logging**: Event streaming with lifecycle, tool usage, and reasoning
- **Cognito Authentication**: Secure user authentication with JWT tokens
- **Serverless Deployment**: ECS Fargate with auto-scaling

## Architecture

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Application Load Balancer          │
│  - Port 80: Gradio UI               │
│  - Port 8000: MongoDB MCP           │
│  - Port 8001: S3 MCP                │
└──────┬──────────────────────────────┘
       │
       ├──────────────────┬────────────────────┐
       ▼                  ▼                    ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Unified App  │   │ MCP Servers  │   │   Cognito    │
│ - Gradio UI  │◄──┤ - MongoDB    │   │ User Pool    │
│ - Strands    │   │ - S3 URLs    │   └──────────────┘
│   Agent      │   │ - Health     │
│ - Bedrock    │   └──────────────┘
│   Model      │          │
└──────┬───────┘          │
       │                  │
       ▼                  ▼
┌──────────────┐   ┌──────────────┐
│   Bedrock    │   │   MongoDB    │
│ Claude 3.5   │   │   Atlas      │
└──────────────┘   └──────────────┘
```

## Repository Structure

```
.
├── infra/
│   └── 2-chatbot-interface/     # Terraform infrastructure code
│       ├── alb.tf               # Application Load Balancer
│       ├── ecs.tf               # ECS cluster and services
│       ├── ecs_services.tf      # MCP server service (commented out)
│       ├── cognito.tf           # User authentication
│       ├── networking.tf        # VPC, subnets, security groups
│       ├── ssm.tf               # Parameter Store configuration
│       └── agent_instruction.txt # Agent system prompt
├── scripts/
│   ├── build_and_deploy.sh     # Deploy unified app
│   ├── build_gradio_ui.sh      # Build unified app image
│   ├── build_mcp_server.sh     # Build MCP servers image
│   └── deploy_gradio_ui.sh     # Update ECS service
├── src/
│   ├── unified_app/            # Gradio + Strands Agent
│   │   ├── app.py              # Main application
│   │   ├── auth.py             # Cognito authentication
│   │   ├── requirements.txt    # Python dependencies
│   │   ├── Dockerfile          # Container configuration
│   │   └── agent_instruction.txt # System prompt
│   └── mcp_servers/            # MCP server containers
│       ├── mongodb_mcp_server.js # Custom MongoDB MCP
│       ├── s3_presigned_server.js # S3 presigned URL MCP
│       ├── package.json        # Node.js dependencies
│       └── Dockerfile          # Multi-server container
└── ARCHITECTURE.md             # Detailed architecture diagram
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.0.0
- Docker with buildx support
- MongoDB Atlas cluster
- AWS Account with:
  - ECS Fargate
  - Amazon Bedrock (Claude 3.5 Sonnet access)
  - Cognito
  - ECR
  - VPC with public/private subnets

## Quick Start

### 1. Deploy Infrastructure

```bash
cd infra/2-chatbot-interface

# Initialize Terraform
terraform init

# Deploy infrastructure
terraform apply \
  -var="environment=dev" \
  -var="mongo_uri=mongodb+srv://user:pass@cluster.mongodb.net" \
  -var="mongo_db=Metadata"
```

### 2. Deploy Unified App

```bash
cd scripts

# Build and deploy unified app (Gradio + Strands Agent)
./build_gradio_ui.sh dev ap-southeast-2
```

### 3. Deploy MCP Servers

```bash
# Build and deploy MCP servers (MongoDB + S3)
./build_mcp_server.sh dev ap-southeast-2
```

### 4. Create Cognito User

```bash
cd infra/2-chatbot-interface

# Get User Pool ID
USER_POOL_ID=$(terraform output -raw cognito_user_pool_id)

# Create user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username testuser \
  --temporary-password TempPass123! \
  --message-action SUPPRESS \
  --region ap-southeast-2

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username testuser \
  --password MyPassword123! \
  --permanent \
  --region ap-southeast-2
```

### 5. Access Application

```bash
# Get ALB DNS name
ALB_DNS=$(terraform output -raw alb_dns_name)
echo "Access application at: http://$ALB_DNS"
```

## Configuration

### SSM Parameters

All configuration is stored in AWS Systems Manager Parameter Store:

- `/datahub-mcp/aws-region` - AWS region
- `/datahub-mcp/mongo-uri` - MongoDB connection string (encrypted)
- `/datahub-mcp/mongo-db` - MongoDB database name
- `/datahub-mcp/alb-dns-name` - ALB DNS for MCP server access
- `/datahub-mcp/cognito-user-pool-id` - Cognito User Pool ID
- `/datahub-mcp/cognito-client-id` - Cognito Client ID

### Environment Variables

Unified App container:
- `AWS_REGION` - AWS region for services
- `GRADIO_SERVER_NAME` - Server bind address (0.0.0.0)
- `GRADIO_ANALYTICS_ENABLED` - Disable analytics (False)

MCP Servers container:
- `MONGO_URI` - MongoDB connection string
- `AWS_REGION` - AWS region for S3 access

## MCP Tools

### MongoDB MCP (Port 8000)

Official MongoDB MCP server provides:
- `find` - Query documents with filters and limits
- `aggregate` - Run aggregation pipelines
- `count` - Count documents matching query
- `list-collections` - List collections in database
- `list-databases` - List available databases
- `connect` - Establish database connection

### S3 Presigned URL MCP (Port 8001)

Custom MCP server provides:
- `generate_presigned_url` - Generate temporary download URLs for S3 datasets
  - Parameters: bucket (default: niwa-data-hub), key, expires_in (default: 3600s)

## Monitoring

### CloudWatch Logs

Logs are organized by service:
- `/ecs/datahub-mcp-dev-gradio-ui` - Unified app logs
  - Event loop lifecycle
  - Tool usage with complete inputs
  - Reasoning process
  - User interactions
- `/ecs/datahub-mcp-dev-mcp-server` - MCP server logs
  - MongoDB queries
  - S3 presigned URL generation
  - Health check status

### Health Checks

- Unified App: ALB checks port 7860 at `/`
- MCP Servers: ALB checks port 8002 at `/health`

## Development

### Local Testing

```bash
# Run MCP servers locally
cd src/mcp_servers
export MONGO_URI="your-mongodb-uri"
export AWS_REGION="ap-southeast-2"
docker compose up

# Run unified app locally
cd src/unified_app
pip install -r requirements.txt
python app.py
```

### Updating Agent Instructions

Edit the system prompt:
```bash
vim infra/2-chatbot-interface/agent_instruction.txt
# Or
vim src/unified_app/agent_instruction.txt
```

Redeploy:
```bash
./build_gradio_ui.sh dev ap-southeast-2
```

## Troubleshooting

### Check ECS Service Status

```bash
aws ecs describe-services \
  --cluster datahub-mcp-dev-cluster \
  --services datahub-mcp-dev-gradio-ui datahub-mcp-dev-mcp-server \
  --region ap-southeast-2
```

### View Logs

```bash
# Unified app logs
aws logs tail /ecs/datahub-mcp-dev-gradio-ui --follow --region ap-southeast-2

# MCP server logs
aws logs tail /ecs/datahub-mcp-dev-mcp-server --follow --region ap-southeast-2
```

### Test MCP Servers

```bash
ALB_DNS=$(cd infra/2-chatbot-interface && terraform output -raw alb_dns_name)

# Test MongoDB MCP
curl http://$ALB_DNS:8000/health

# Test S3 MCP
curl http://$ALB_DNS:8001/mcp/tools
```

## Architecture Details

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture diagrams and component descriptions.

## License

Internal NIWA project. 
