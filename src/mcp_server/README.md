# MCP Server

This is the MCP (Model Context Protocol) server for the Data Platform project.

## Configuration

The MCP server uses AWS Systems Manager Parameter Store for configuration. The following parameters are required:

- `/remote-mcp-server/aws-region`: AWS region (default: ap-southeast-2)
- `/remote-mcp-server/mongo-uri`: MongoDB connection URI
- `/remote-mcp-server/mongo-db`: MongoDB database name
- `/remote-mcp-server/mongodb-mcp-server-url`: URL of the MongoDB MCP server
- `/remote-mcp-server/mcp-server-url`: URL of the main MCP server
- `/remote-mcp-server/cognito-user-pool-id`: Cognito User Pool ID
- `/remote-mcp-server/cognito-client-id`: Cognito Client ID
- `/remote-mcp-server/bedrock-agent-id`: Bedrock Agent ID
- `/remote-mcp-server/bedrock-agent-alias-id`: Bedrock Agent Alias ID

## Setting Up Parameters

### Step 1: Deploy Infrastructure

First, deploy the infrastructure using Terraform:

```bash
cd ../../infra/2-chatbot-interface
export PROJECT_CODE=FPEI2606
export PROJECT_NAME=data-platform-remote-mcp-server
export ENVIRONMENT=dev
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
terraform init -backend-config="bucket=${PROJECT_NAME}-${ENVIRONMENT}-${AWS_ACCOUNT_ID}-terraform-state" -backend-config="key=${PROJECT_CODE}/${PROJECT_NAME}/${ENVIRONMENT}.tfstate"
terraform plan -var="environment=${ENVIRONMENT}" -var="mongo_uri=your-mongodb-uri" -var="mongo_db=data_platform"
terraform apply -var="environment=${ENVIRONMENT}" -var="mongo_uri=your-mongodb-uri" -var="mongo_db=data_platform"
```

### Step 2: Get Infrastructure Outputs

After the infrastructure is deployed, get the required values:

```bash
# Get all outputs
terraform output

# Or get specific outputs
echo "COGNITO_USER_POOL_ID=$(terraform output -raw cognito_user_pool_id)"
echo "COGNITO_CLIENT_ID=$(terraform output -raw cognito_client_id)"
echo "BEDROCK_AGENT_ID=$(terraform output -raw bedrock_agent_id)"
echo "BEDROCK_AGENT_ALIAS_ID=$(terraform output -raw bedrock_agent_alias_id)"
echo "MCP_SERVER_URL=http://$(terraform output -raw mcp_server_private_ip):8000"
echo "MONGODB_MCP_SERVER_URL=http://$(terraform output -raw mcp_server_private_ip):8001"
```

### Step 3: Create .env File and Upload Parameters

1. Create a `.env` file with the infrastructure outputs:

```bash
# Required parameters
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net
MONGO_DB=data_platform

# Infrastructure outputs (get these from terraform output)
COGNITO_USER_POOL_ID=ap-southeast-2_xxxxxxxxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
BEDROCK_AGENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
BEDROCK_AGENT_ALIAS_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
MCP_SERVER_URL=http://10.0.1.100:8000
MONGODB_MCP_SERVER_URL=http://10.0.1.100:8001
AWS_REGION=ap-southeast-2
```

2. Run the upload script:

```bash
cd ../../scripts
python upload_params_to_ssm.py --env-file .env --prefix /remote-mcp-server --region ap-southeast-2
```

### Alternative: Manual Parameter Creation

You can also create parameters manually using AWS CLI:

```bash
# Required parameters
aws ssm put-parameter --name "/remote-mcp-server/mongo-uri" --value "mongodb://username:password@hostname:27017" --type "SecureString" --overwrite
aws ssm put-parameter --name "/remote-mcp-server/mongo-db" --value "data_platform" --type "String" --overwrite

# Infrastructure-dependent parameters (use terraform outputs)
aws ssm put-parameter --name "/remote-mcp-server/cognito-user-pool-id" --value "$(terraform output -raw cognito_user_pool_id)" --type "String" --overwrite
aws ssm put-parameter --name "/remote-mcp-server/cognito-client-id" --value "$(terraform output -raw cognito_client_id)" --type "String" --overwrite
aws ssm put-parameter --name "/remote-mcp-server/bedrock-agent-id" --value "$(terraform output -raw bedrock_agent_id)" --type "String" --overwrite
aws ssm put-parameter --name "/remote-mcp-server/bedrock-agent-alias-id" --value "$(terraform output -raw bedrock_agent_alias_id)" --type "String" --overwrite
```

## Local Development

For local development, you can use a `.env` file with the same parameters. The application will fall back to environment variables if SSM parameters are not available.

## IAM Permissions

The EC2 instance or ECS task running this application needs the following IAM permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/remote-mcp-server/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:*",
                "bedrock-runtime:*"
            ],
            "Resource": "*"
        }
    ]
}
```

Note: These permissions are automatically configured when using the Terraform infrastructure.