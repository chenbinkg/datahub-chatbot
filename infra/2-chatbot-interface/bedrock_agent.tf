# Read agent instruction from file
data "local_file" "agent_instruction" {
  filename = "${path.module}/agent_instruction.txt"
}

# Bedrock Agent
resource "aws_bedrockagent_agent" "mcp_agent" {
  agent_name        = "${local.name_prefix}-agent"
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model  = "anthropic.claude-3-5-sonnet-20241022-v2:0"
  
  instruction = data.local_file.agent_instruction.content
  
  idle_session_ttl_in_seconds = 1800
  
  memory_configuration {
    enabled_memory_types = ["SESSION_SUMMARY"]
    storage_days = 30
  }
  
  tags = local.tags
}

# Bedrock Agent Action Group
resource "aws_bedrockagent_agent_action_group" "mcp_action_group" {
  agent_id          = aws_bedrockagent_agent.mcp_agent.id
  action_group_name = "${local.name_prefix}-action-group"
  agent_version     = "DRAFT"
  
  action_group_executor {
    lambda  = aws_lambda_function.mcp_agent_lambda.arn
  }
  
  description = "Optional action group for interacting with MCP servers when specialized capabilities are needed"
  
  action_group_state = "ENABLED"
  
  api_schema {
    payload = jsonencode({
      openapi = "3.0.0"
      info = {
        title   = "MCP API"
        version = "1.0.0"
      }
      paths = {
        "/process" = {
          post = {
            summary     = "Process a query through an MCP server"
            description = "Send a query to an MCP server for processing"
            operationId = "processQuery"
            requestBody = {
              required = true
              content = {
                "application/json" = {
                  schema = {
                    type = "object"
                    required = ["query"]
                    properties = {
                      query = {
                        type        = "string"
                        description = "The query to process"
                      }
                      parameters = {
                        type        = "object"
                        description = "Optional parameters for the MCP"
                      }
                    }
                  }
                }
              }
            }
            responses = {
              "200" = {
                description = "Successful response"
                content = {
                  "application/json" = {
                    schema = {
                      type = "object"
                      properties = {
                        result = {
                          type = "object"
                          description = "The result of the query"
                        }
                        status = {
                          type = "string"
                          description = "The status of the request"
                        }
                        message = {
                          type = "string"
                          description = "Any message associated with the request"
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    })
  }
}

# workaround for agent version change: https://github.com/hashicorp/terraform-provider-aws/issues/37321
# This is an ephemeral alias that gets recreated whenever the agent is changed
resource "aws_bedrockagent_agent_alias" "ephemeral" {
  agent_id         = aws_bedrockagent_agent.mcp_agent.id
  agent_alias_name = "myagent-ephemeral"

  description = "Ephemeral alias used as a hack to trigger new agent version creation."

  lifecycle {
    replace_triggered_by = [
      aws_bedrockagent_agent.mcp_agent
    ]
  }
}

# Bedrock Agent Alias
resource "aws_bedrockagent_agent_alias" "mcp_agent_alias" {
  agent_id         = aws_bedrockagent_agent.mcp_agent.id
  agent_alias_name = "${local.name_prefix}-alias"
  description      = "Alias for MCP agent"
  
  depends_on = [
    aws_bedrockagent_agent_action_group.mcp_action_group
  ]
  routing_configuration {
    agent_version = aws_bedrockagent_agent_alias.ephemeral.routing_configuration[0].agent_version
  }
  tags = local.tags
}