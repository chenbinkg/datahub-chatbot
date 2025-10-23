# SSM Parameters for configuration
resource "aws_ssm_parameter" "aws_region" {
  name  = "/datahub-mcp/aws-region"
  type  = "String"
  value = var.aws_region
  tags  = local.tags
}

# MCP server URLs will be service discovery based or internal load balancer
# For now, using service names that resolve within the VPC
resource "aws_ssm_parameter" "mcp_server_url" {
  name  = "/datahub-mcp/mcp-server-url"
  type  = "String"
  value = "http://${aws_lb.main.dns_name}:8000"
  tags  = local.tags
}

resource "aws_ssm_parameter" "mongodb_mcp_server_url" {
  name  = "/datahub-mcp/mongodb-mcp-server-url"
  type  = "String"
  value = "http://${aws_lb.main.dns_name}:8001"
  tags  = local.tags
}

resource "aws_ssm_parameter" "alb_dns_name" {
  name  = "/datahub-mcp/alb-dns-name"
  type  = "String"
  value = aws_lb.main.dns_name
  tags  = local.tags
}

resource "aws_ssm_parameter" "cognito_user_pool_id" {
  name  = "/datahub-mcp/cognito-user-pool-id"
  type  = "String"
  value = aws_cognito_user_pool.main.id
  tags  = local.tags
}

resource "aws_ssm_parameter" "cognito_client_id" {
  name  = "/datahub-mcp/cognito-client-id"
  type  = "String"
  value = aws_cognito_user_pool_client.client.id
  tags  = local.tags
}

# These parameters need to be set manually or through the upload script
resource "aws_ssm_parameter" "mongo_uri" {
  name  = "/datahub-mcp/mongo-uri"
  type  = "SecureString"
  value = var.mongo_uri
  tags  = local.tags
}

resource "aws_ssm_parameter" "mongo_db" {
  name  = "/datahub-mcp/mongo-db"
  type  = "String"
  value = var.mongo_db
  tags  = local.tags
}

# # Placeholder parameters for Bedrock agent (will be updated when Bedrock agent resources are supported)
# resource "aws_ssm_parameter" "bedrock_agent_id" {
#   name  = "/datahub-mcp/bedrock-agent-id"
#   type  = "String"
#   value = aws_bedrockagent_agent.mcp_agent.id
#   tags  = local.tags
# }

# resource "aws_ssm_parameter" "bedrock_agent_alias_id" {
#   name  = "/datahub-mcp/bedrock-agent-alias-id"
#   type  = "String"
#   value = aws_bedrockagent_agent_alias.mcp_agent_alias.agent_alias_id
#   tags  = local.tags
# }
