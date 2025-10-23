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
export PROJECT_NAME=datahub-mcp
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
- Bedrock Agent and Alias with Knowledge Base
<!-- - Neptune Analytics Graph for taxonomy -->
- S3 bucket for knowledge base documents
- All necessary networking and IAM roles

## Step 3: Build and Deploy Containers

### Option A: Using Build Scripts

**Deploy Both Services:**
```bash
cd ../../scripts
./build_and_deploy.sh dev ap-southeast-2
```

**Deploy Only MCP Server:**
```bash
cd ../../scripts
./build_mcp_server.sh dev ap-southeast-2
```

**Deploy Only Gradio UI:**
```bash
cd ../../scripts
./build_gradio_ui.sh dev ap-southeast-2
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
aws ecs update-service --cluster <cluster-name> --service <mcp-service-name> --force-new-deployment --desired-count 1 --region ap-southeast-2
aws ecs update-service --cluster <cluster-name> --service <gradio-service-name> --force-new-deployment --desired-count 1 --region ap-southeast-2
```

For example, for gradio-ui ECS service in dev environment, restart the service like this:
```bash
aws ecs update-service \
  --cluster datahub-mcp-dev-cluster \
  --service datahub-mcp-dev-gradio-ui \
  --force-new-deployment \
  --desired-count 1 \
  --region ap-southeast-2 \
  --no-cli-pager
```

For mcp-server ECS service in dev environment, restart the service like this:
```bash
aws ecs update-service \
  --cluster datahub-mcp-dev-cluster \
  --service datahub-mcp-dev-mcp-server \
  --force-new-deployment \
  --desired-count 1 \
  --region ap-southeast-2 \
  --no-cli-pager 

# Wait 30 seconds, then scale back up
sleep 30

aws ecs update-service \
  --cluster datahub-mcp-dev-cluster \
  --service datahub-mcp-dev-mcp-server \
  --force-new-deployment \
  --desired-count 1 \
  --region ap-southeast-2 \
  --no-cli-pager 

```

Double check that the ECS services have been trimed down to 1 for each of the above.
```bash
aws ecs describe-services \
  --cluster datahub-mcp-dev-cluster \
  --services datahub-mcp-dev-gradio-ui \
  --region ap-southeast-2 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Deployment:deployments[0].status}'
```

```bash
aws ecs describe-services \
  --cluster datahub-mcp-dev-cluster \
  --services datahub-mcp-dev-mcp-server \
  --region ap-southeast-2 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Deployment:deployments[0].status}'
```

## Step 4: Create Cognito Users

Create users for authentication:

```bash
cd infra/2-chatbot-interface

# Get Cognito User Pool ID
USER_POOL_ID=$(terraform output -raw cognito_user_pool_id)

# Create a user (email as username)
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username user@example.com \
  --user-attributes Name=email,Value=user@example.com Name=email_verified,Value=true \
  --temporary-password TempPass123! \
  --message-action SUPPRESS \
  --region ap-southeast-2

# Set permanent password (skips force change password)
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username user@example.com \
  --password MyPassword123! \
  --permanent \
  --region ap-southeast-2

```

## Step 5: Setup Taxonomy Knowledge Base

Upload DTIS taxonomy data to the GraphRAG knowledge base:

```bash
cd dtis_ontology

# Upload taxonomy data to knowledge base
python upload_taxonomy_to_kb.py

# Check ingestion status
KB_ID=$(cd ../infra/2-chatbot-interface && terraform output -raw knowledge_base_id)
aws bedrock-agent list-ingestion-jobs --knowledge-base-id $KB_ID --region ap-southeast-2

# Test knowledge base
aws bedrock-agent-runtime retrieve \
  --knowledge-base-id $KB_ID \
  --retrieval-query '{"text": "What is Stylasteridae?"}' \
  --region ap-southeast-2
```

**Note**: Ingestion may take 5-10 minutes. The chatbot will have enhanced taxonomy knowledge once complete.

## Step 6: Access the Application

1. Get the ALB DNS name:
```bash
terraform output alb_dns_name
```

2. Access the Gradio UI at: `http://<alb-dns-name>`

3. **Login credentials:**
   - Username: `user@example.com`
   - Password: `MyPassword123!`

4. **Usage:**
   - Click **Login** tab first
   - Enter credentials and login
   - Switch to **Chat** tab to interact with MCP server
   - Ask taxonomy questions like "What is Stylasteridae?" to test knowledge base

5. **Password Management:**
   
   **Note**: Cognito Hosted UI is not available due to HTTP callback URL limitations.
   
   **For password changes, users must contact admin who can reset passwords:**
   ```bash
   # Admin resets user password
   aws cognito-idp admin-set-user-password \
     --user-pool-id $(terraform output -raw cognito_user_pool_id) \
     --username user@example.com \
     --password NewPassword123! \
     --permanent \
     --region ap-southeast-2
   ```

## Local Development

### Test Docker Images Locally First:

**Test Gradio UI:**
```bash
cd src/gradio_ui
docker build -t gradio-ui-test .
docker run -p 7860:7860 gradio-ui-test
# Access: http://localhost:7860
# Note: Login won't work locally (requires AWS Cognito)
```

**Test MCP Server:**
```bash
cd src/mcp_server
docker build -t mcp-server-test .
docker run -p 8000:8000 -p 8001:8001 mcp-server-test
# Access: http://localhost:8000
```

### Alternative - Docker Compose:
```bash
cd src/mcp_server
docker-compose up
```

### Access locally:
- Gradio UI: `http://localhost:7860`
- MCP Server: `http://localhost:8000`
- MongoDB MCP Server: `http://localhost:8001`
- Local MongoDB: `mongodb://admin:password@localhost:27017`

## Troubleshooting

1. **Check ECS service status**:
```bash
aws ecs describe-services \
  --cluster datahub-mcp-dev-cluster \
  --services datahub-mcp-dev-gradio-ui \
  --region ap-southeast-2 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Deployment:deployments[0].status}'
```

```bash
aws ecs describe-services \
  --cluster datahub-mcp-dev-cluster \
  --services datahub-mcp-dev-mcp-server \
  --region ap-southeast-2 \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Deployment:deployments[0].status}'
```

Deployment Complete When:
- Status: "ACTIVE"
- Running: 1, Desired: 1 (or your desired count)
- Deployment: "PRIMARY"

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

4. **Authentication Issues**:
```bash
# If login fails, check Cognito user exists
aws cognito-idp list-users --user-pool-id $(terraform output -raw cognito_user_pool_id) --region ap-southeast-2

# Reset user password if needed
aws cognito-idp admin-set-user-password \
  --user-pool-id $(terraform output -raw cognito_user_pool_id) \
  --username user@example.com \
  --password NewPassword123! \
  --permanent \
  --region ap-southeast-2
```

5. **"Session Not Found" Error**:
```bash
# Check if multiple Gradio UI tasks are running (causes session issues)
aws ecs describe-services \
  --cluster datahub-mcp-dev-cluster \
  --services datahub-mcp-dev-gradio-ui \
  --region ap-southeast-2 \
  --query 'services[0].{Running:runningCount,Desired:desiredCount}'

# If Running > 1, scale down to 1 task
aws ecs update-service \
  --cluster datahub-mcp-dev-cluster \
  --service datahub-mcp-dev-gradio-ui \
  --force-new-deployment \
  --desired-count 1 \
  --region ap-southeast-2

# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups --names datahub-mcp-dev-tg --query 'TargetGroups[0].TargetGroupArn' --output text) \
  --region ap-southeast-2

# Clear browser cache and cookies, then try again
# Or try incognito/private browsing mode
```

6. **Login Returns "False" Status**:
```bash
# Check Gradio UI container logs for authentication errors
aws logs tail /ecs/datahub-mcp-dev-gradio-ui --follow --region ap-southeast-2

# Verify Cognito configuration in SSM parameters
aws ssm get-parameters \
  --names "/datahub-mcp/cognito-user-pool-id" "/datahub-mcp/cognito-client-id" \
  --region ap-southeast-2

# Check if Cognito client has secret configured (this causes the issue)
aws cognito-idp describe-user-pool-client \
  --user-pool-id $(terraform output -raw cognito_user_pool_id) \
  --client-id $(terraform output -raw cognito_client_id) \
  --region ap-southeast-2 \
  --query 'UserPoolClient.{ClientSecret:ClientSecret,GenerateSecret:GenerateSecret}'

# If client has secret, you need to update Terraform to disable it
# The Gradio app doesn't handle client secrets properly

# Check if user is enabled and confirmed
aws cognito-idp admin-get-user \
  --user-pool-id $(terraform output -raw cognito_user_pool_id) \
  --username user@example.com \
  --region ap-southeast-2
```

7. **Chat Error: "Data incompatible with tuples format"**:
```bash
# This is a Gradio chatbot format issue
# Check Gradio UI logs for the specific error
aws logs tail /ecs/datahub-mcp-dev-gradio-ui --follow --region ap-southeast-2

# The error occurs when chat responses don't match expected format
# Each message should be [user_message, bot_response] format
# This needs to be fixed in the Gradio app.py code
```

8. **Bedrock Agent sessionState Parameter Error**:
```bash
# Error: Unknown parameter in sessionState: "mcp_type"
# This means custom parameters can't be passed in sessionState
# The mcp_type should be included in the input text instead
# Check Gradio UI logs for Bedrock agent errors
aws logs tail /ecs/datahub-mcp-dev-gradio-ui --follow --region ap-southeast-2
```

9. **Bedrock Agent ID/Alias Validation Error**:
```bash
# Error: agentAliasId validation failed (length/pattern)
# Check if SSM parameters contain correct values
aws ssm get-parameters \
  --names "/datahub-mcp/bedrock-agent-id" "/datahub-mcp/bedrock-agent-alias-id" \
  --region ap-southeast-2

# Get correct values from Terraform outputs
cd infra/2-chatbot-interface
terraform output bedrock_agent_id
terraform output bedrock_agent_alias_id

# Update SSM parameters if needed
aws ssm put-parameter \
  --name "/datahub-mcp/bedrock-agent-id" \
  --value "$(terraform output -raw bedrock_agent_id)" \
  --type "String" \
  --overwrite \
  --region ap-southeast-2

aws ssm put-parameter \
  --name "/datahub-mcp/bedrock-agent-alias-id" \
  --value "$(terraform output -raw bedrock_agent_alias_id)" \
  --type "String" \
  --overwrite \
  --region ap-southeast-2
```

10. **Knowledge Base Issues**:
```bash
# Check knowledge base status
KB_ID=$(terraform output -raw knowledge_base_id)
aws bedrock-agent get-knowledge-base --knowledge-base-id $KB_ID --region ap-southeast-2

# Check ingestion jobs
aws bedrock-agent list-ingestion-jobs --knowledge-base-id $KB_ID --region ap-southeast-2

# Re-upload taxonomy data if needed
cd dtis_ontology
python upload_taxonomy_to_kb.py

# Test knowledge base retrieval
aws bedrock-agent-runtime retrieve \
  --knowledge-base-id $KB_ID \
  --retrieval-query '{"text": "taxonomy hierarchy"}' \
  --region ap-southeast-2
```

11. **MCP Server Node.js/Python Dependency Errors**:
```bash
# Error: Node.js version too old or missing Python modules
# Check MCP server logs
aws logs tail /ecs/datahub-mcp-dev-mcp-server --follow --region ap-southeast-2

# The MCP server Dockerfile needs:
# - Node.js 20 (not 18) for MongoDB MCP server
# - requests module in pixi dependencies
# Rebuild MCP server after fixing Dockerfile
cd scripts
./build_mcp_server.sh dev ap-southeast-2
```nt_alias_id

# Update SSM parameters if needed
aws ssm put-parameter \
  --name "/datahub-mcp/bedrock-agent-id" \
  --value "$(terraform output -raw bedrock_agent_id)" \
  --type "String" \
  --overwrite \
  --region ap-southeast-2

aws ssm put-parameter \
  --name "/datahub-mcp/bedrock-agent-alias-id" \
  --value "$(terraform output -raw bedrock_agent_alias_id)" \
  --type "String" \
  --overwrite \
  --region ap-southeast-2
```