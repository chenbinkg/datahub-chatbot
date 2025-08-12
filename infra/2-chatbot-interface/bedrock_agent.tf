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
- Complex reasoning/planning → AUTOMATICALLY use sequential_thinking MCP
- General questions → Answer directly with your knowledge

**IMPORTANT:** 
- NEVER ask "what MCP type should I use?"
- NEVER ask users to specify mongodb, aws, or sequential_thinking
- ALWAYS choose the most appropriate tool automatically
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

# IAM Role for Bedrock Agent
resource "aws_iam_role" "bedrock_agent_role" {
  name = "${local.name_prefix}-bedrock-agent-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
          ArnLike = {
            "AWS:SourceArn" = "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:agent/*"
          }
        }
      }
    ]
  })
  
  tags = local.tags
}

# IAM Policy for Bedrock Agent
resource "aws_iam_role_policy" "bedrock_agent_policy" {
  name = "${local.name_prefix}-bedrock-agent-policy"
  role = aws_iam_role.bedrock_agent_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "lambda:InvokeFunction"
        ]
        Effect   = "Allow"
        Resource = aws_lambda_function.mcp_agent_lambda.arn
      },
      {
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/anthropic.claude-*-sonnet-*"
      }
    ]
  })
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${local.name_prefix}-mcp-agent-lambda"
  retention_in_days = 14
  tags = local.tags
}

# Lambda Function for Bedrock Agent
resource "aws_lambda_function" "mcp_agent_lambda" {
  function_name = "${local.name_prefix}-mcp-agent-lambda"
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  
  filename      = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  
  vpc_config {
    subnet_ids         = module.vpc.private_subnets
    security_group_ids = [aws_security_group.lambda.id]
  }
  
  environment {
    variables = {
      MCP_SERVER_URL = "http://${aws_lb.main.dns_name}:8000"
    }
  }
  
  depends_on = [aws_cloudwatch_log_group.lambda_logs]
  tags = local.tags
}

# Lambda permission for Bedrock Agent to invoke
resource "aws_lambda_permission" "bedrock_agent_invoke" {
  statement_id  = "AllowBedrockAgentInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.mcp_agent_lambda.function_name
  principal     = "bedrock.amazonaws.com"
  source_arn    = "arn:aws:bedrock:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:agent/${aws_bedrockagent_agent.mcp_agent.id}"
}

# Lambda IAM Role
resource "aws_iam_role" "lambda_role" {
  name = "${local.name_prefix}-lambda-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = local.tags
}

# Lambda Basic Execution Policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda VPC Access Policy
resource "aws_iam_role_policy_attachment" "lambda_vpc_access" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# Lambda additional permissions for MCP server access
resource "aws_iam_role_policy" "lambda_mcp_access" {
  name = "${local.name_prefix}-lambda-mcp-access"
  role = aws_iam_role.lambda_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "ssm:GetParameter"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:ssm:*:*:parameter/remote-mcp-server/*"
      }
    ]
  })
}

# Lambda Security Group
resource "aws_security_group" "lambda" {
  name        = "${local.name_prefix}-lambda-sg"
  description = "Security group for Lambda function"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

# Lambda Code
data "archive_file" "lambda_zip" {
  type        = "zip"
  output_path = "${path.module}/lambda_function.zip"
  
  source {
    content  = <<EOF
import json
import os
import urllib3
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize HTTP client
http = urllib3.PoolManager()

def lambda_handler(event, context):
    logger.info(f"Lambda invoked with event: {json.dumps(event, indent=2)}")
    
    try:
        action_group = event.get('actionGroup')
        api_path = event.get('apiPath')
        
        # Extract parameters from requestBody (Bedrock Agent format)
        request_body = event.get('requestBody', {})
        content = request_body.get('content', {})
        app_json = content.get('application/json', {})
        properties = app_json.get('properties', [])
        
        logger.info(f"Processing properties: {properties}")
        
        # Convert properties to parameter map
        param_map = {}
        for prop in properties:
            param_map[prop['name']] = prop['value']
        
        logger.info(f"Parameter map: {param_map}")
        
        # Prepare request to MCP server
        # Handle parameters - try to parse as JSON, otherwise use as string
        parameters_raw = param_map.get('parameters', '{}')
        try:
            if parameters_raw.startswith('{') and parameters_raw.endswith('}'):
                parameters = json.loads(parameters_raw)
            else:
                # If it's not JSON, treat it as a string parameter
                parameters = {'raw_parameters': parameters_raw}
        except json.JSONDecodeError:
            parameters = {'raw_parameters': parameters_raw}
        
        # Ensure mcp_type always has a value
        mcp_type = param_map.get('mcp_type')
        if not mcp_type:
            mcp_type = 'mongodb'  # Default to mongodb
            logger.info(f"No mcp_type provided, defaulting to: {mcp_type}")
        
        mcp_request = {
            'query': param_map.get('query'),
            'mcp_type': mcp_type,
            'parameters': parameters
        }
        
        logger.info(f"Final MCP request: {mcp_request}")
        
        logger.info(f"Request body for MCP server: {mcp_request}")
        
        # Validate required fields
        if not mcp_request['query']:
            raise ValueError("Query parameter is required")
        
        # Ensure mcp_type is valid
        valid_mcp_types = ['mongodb', 'mongodb_external', 'aws', 'sequential_thinking']
        if mcp_request['mcp_type'] not in valid_mcp_types:
            logger.warning(f"Invalid mcp_type: {mcp_request['mcp_type']}, defaulting to mongodb")
            mcp_request['mcp_type'] = 'mongodb'
        
        # Call MCP server
        mcp_server_url = os.environ.get('MCP_SERVER_URL', 'http://localhost:8000')
        url = f"{mcp_server_url}/process"
        
        logger.info(f"Calling MCP server at: {url}")
        
        response = http.request(
            'POST',
            url,
            body=json.dumps(mcp_request),
            headers={'Content-Type': 'application/json'}
        )
        
        logger.info(f"MCP server response status: {response.status}")
        logger.info(f"Raw MCP server response: {response.data.decode('utf-8')}")
        
        if response.status == 200:
            mcp_response = json.loads(response.data.decode('utf-8'))
        else:
            mcp_response = {
                'status': 'error',
                'message': f'MCP server returned status {response.status}',
                'details': response.data.decode('utf-8')
            }
        
        logger.info(f"MCP server parsed response: {mcp_response}")
        
        # Format response for Bedrock Agent
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': action_group,
                'apiPath': api_path,
                'httpMethod': 'POST',
                'httpStatusCode': 200,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(mcp_response)
                    }
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Lambda error: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        error_response = {
            'status': 'error',
            'message': str(e),
            'type': type(e).__name__
        }
        
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup'),
                'apiPath': event.get('apiPath'),
                'httpMethod': 'POST',
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(error_response)
                    }
                }
            }
        }
EOF
    filename = "lambda_function.py"
  }
}