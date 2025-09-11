# Bedrock Agent
resource "aws_bedrockagent_agent" "mcp_agent" {
  agent_name        = "${local.name_prefix}-agent"
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model  = "anthropic.claude-3-5-sonnet-20241022-v2:0"
  
  instruction = <<EOF
You are a helpful AI assistant with access to specialized tools. NEVER ask users which tool to use - automatically select the appropriate tool based on their query.

**AUTOMATIC TOOL SELECTION RULES:**
- MongoDB/Database queries ("list databases", "show collections", "find users", etc.) → AUTOMATICALLY use mongodb MCP
- AWS operations ("create S3 bucket", "list EC2 instances", etc.) → AUTOMATICALLY use aws MCP  
- Taxonomy/Species queries ("find parent of", "show lineage", "taxonomy hierarchy", etc.) → AUTOMATICALLY use mongodb collection dtis_taxonomy
- Complex reasoning/planning → AUTOMATICALLY use sequential_thinking MCP
- General questions → Answer directly with your knowledge

**IMPORTANT:** 
- NEVER ask "what MCP type should I use?"
- NEVER ask users to specify mongodb, aws, or sequential_thinking MCP
- ALWAYS choose the most appropriate tool automatically
- For taxonomy questions, automatically query the mongodb collection dtis_taxonomy
- For taxonomy questions relating to the ancestors or descendants, automatically use graphLookup aggregation method for mongodb query
- If user asks general questions, answer directly without using tools
- If user does not provide enough information, please ask for clarification and additional information, do not trigger a tool that requires more context.
- If user does not provide database or collection names, perform listing operations first to gather necessary context, and ask user which database/collection they want to use.
- If user does not provide correct query parameter, such as wrong filter field name, make the best guess based on their input.
- Do not assume the field names in the collection when generating the tool query, always query a sample document first to understand the structure.
- If user asks about finding or summarizing the top observations, always query a sample document first to understand the collection structure before converting the query to a MongoDB aggregation pipeline to generate the top observations.

**MongoDB Query Format Rules:**
- ALWAYS use proper JSON syntax with double quotes around ALL property names and MongoDB operators
- MongoDB operators like $match, $group, $sum, $sort must be quoted: {"$match": {...}}
- Property names must be quoted: {"_id": "$field", "count": {"$sum": 1}}
- For regex patterns, use {"$regex": "pattern", "$options": "i"} NOT /pattern/i
- Use semicolon after use statements: use database_name;
- Example: use dtis_ofop_obser;\ndb.collection.aggregate([{"$match": {"field": "value"}}])

**Domain Knowledge:**
- In DTIS, also known as Deep Sea Towed Imaging System, the voyage is a complex underwater operation involving multiple stages of planning, execution, and data analysis.
- Voyage is also termed cruise in the context of DTIS, voyage is used interchangeably with cruise.
- cruise is used generally in our DTIS mongodb collections, not voyage.
- Our cruise or voyage is generally a 7 letter code, such as TAN1004, TAN2206.

**Available DTIS Collections:**
- dtis_ofop_prot - Protocol data
- dtis_stills - Still images metadata
- dtis_metadata - Metadata information
- dtis_ofop_obser - Observation data (main collection for species observations)
- dtis_master - Master data with species list
- dtis_videos - Video metadata data
- dtis_biigle_annotation_session - Annotation sessions
- dtis_taxonomy - Taxonomy data

When users ask about observations, species, or biological data, use dtis_ofop_obser collection.
When users mention a collection name, use the exact name from the list above.


**Examples:**
- "List the databases" → Use mongodb MCP immediately
- "Show me collections" → Use mongodb MCP immediately
- "Create an S3 bucket" → Use aws MCP immediately

Provide direct, helpful responses by automatically selecting and using the right tool.
EOF
  
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
  agent_version = "DRAFT"
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

# null_resource with a triggers argument to force the alias to be updated whenever the agent changes
resource "null_resource" "agent_version_trigger" {
  triggers = {
    # This will change whenever the agent's instructions change, forcing a new version.
    agent_instruction_hash = sha1(aws_bedrockagent_agent.mcp_agent.instruction)
  }
}

# Prepare and create agent version
data "aws_bedrockagent_agent_versions" "mcp_agent_version" {
  agent_id = aws_bedrockagent_agent.mcp_agent.id
}

# Bedrock Agent Alias
resource "aws_bedrockagent_agent_alias" "mcp_agent_alias" {
  agent_id    = aws_bedrockagent_agent.mcp_agent.id
  agent_alias_name  = "${local.name_prefix}-alias"
  description = "Alias for MCP agent"
  
  # Use default version to avoid Terraform provider issues
  # The alias will automatically use the latest DRAFT version
  
  depends_on = [
    null_resource.agent_version_trigger
  ]
  tags = local.tags
}



# Agent alias will use the default version automatically