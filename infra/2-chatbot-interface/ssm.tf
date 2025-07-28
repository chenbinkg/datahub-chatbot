# SSM Parameters for configuration
resource "aws_ssm_parameter" "aws_region" {
  name  = "/remote-mcp-server/aws-region"
  type  = "String"
  value = var.aws_region
  tags  = local.tags
}

# MCP server URLs will be service discovery based or internal load balancer
# For now, using service names that resolve within the VPC
resource "aws_ssm_parameter" "mcp_server_url" {
  name  = "/remote-mcp-server/mcp-server-url"
  type  = "String"
  value = "http://${local.name_prefix}-mcp-server.${local.name_prefix}-cluster.local:8000"
  tags  = local.tags
}

resource "aws_ssm_parameter" "mongodb_mcp_server_url" {
  name  = "/remote-mcp-server/mongodb-mcp-server-url"
  type  = "String"
  value = "http://${local.name_prefix}-mcp-server.${local.name_prefix}-cluster.local:8001"
  tags  = local.tags
}

resource "aws_ssm_parameter" "cognito_user_pool_id" {
  name  = "/remote-mcp-server/cognito-user-pool-id"
  type  = "String"
  value = aws_cognito_user_pool.main.id
  tags  = local.tags
}

resource "aws_ssm_parameter" "cognito_client_id" {
  name  = "/remote-mcp-server/cognito-client-id"
  type  = "String"
  value = aws_cognito_user_pool_client.client.id
  tags  = local.tags
}

# These parameters need to be set manually or through the upload script
resource "aws_ssm_parameter" "mongo_uri" {
  name  = "/remote-mcp-server/mongo-uri"
  type  = "SecureString"
  value = var.mongo_uri
  tags  = local.tags
}

resource "aws_ssm_parameter" "mongo_db" {
  name  = "/remote-mcp-server/mongo-db"
  type  = "String"
  value = var.mongo_db
  tags  = local.tags
}

# Placeholder parameters for Bedrock agent (will be updated when Bedrock agent resources are supported)
resource "aws_ssm_parameter" "bedrock_agent_id" {
  name  = "/remote-mcp-server/bedrock-agent-id"
  type  = "String"
  value = aws_bedrockagent_agent.mcp_agent.id
  tags  = local.tags
}

resource "aws_ssm_parameter" "bedrock_agent_alias_id" {
  name  = "/remote-mcp-server/bedrock-agent-alias-id"
  type  = "String"
  value = aws_bedrockagent_agent_alias.mcp_agent_alias.id
  tags  = local.tags
}