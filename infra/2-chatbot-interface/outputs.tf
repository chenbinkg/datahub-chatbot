output "alb_dns_name" {
  description = "The DNS name of the load balancer"
  value       = aws_lb.main.dns_name
}

output "cognito_user_pool_id" {
  description = "The ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  description = "The ID of the Cognito User Pool Client"
  value       = aws_cognito_user_pool_client.client.id
}

# MCP server is now containerized, no EC2 instance
# output "mcp_server_private_ip" {
#   description = "The private IP address of the MCP server"
#   value       = aws_instance.mcp_server.private_ip
# }

output "ecr_repository_url" {
  description = "The URL of the Gradio UI ECR repository"
  value       = aws_ecr_repository.gradio_ui.repository_url
}

output "ecr_mcp_server_url" {
  description = "The URL of the MCP Server ECR repository"
  value       = aws_ecr_repository.mcp_server.repository_url
}

output "vpc_id" {
  description = "The ID of the VPC"
  value       = module.vpc.vpc_id
}

output "private_subnets" {
  description = "List of IDs of private subnets"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "List of IDs of public subnets"
  value       = module.vpc.public_subnets
}

output "bedrock_agent_id" {
  description = "The ID of the Bedrock Agent"
  value       = aws_bedrockagent_agent.mcp_agent.id
}

output "bedrock_agent_alias_id" {
  description = "The ID of the Bedrock Agent Alias"
  value       = aws_bedrockagent_agent_alias.mcp_agent_alias.id
}
