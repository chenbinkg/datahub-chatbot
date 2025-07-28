# Bedrock Agent
resource "aws_bedrock_agent" "mcp_agent" {
  agent_name        = "${local.name_prefix}-agent"
  agent_resource_role_arn = aws_iam_role.bedrock_agent_role.arn
  foundation_model  = "anthropic.claude-3-sonnet-20240229-v1:0"
  
  instruction = "You are an AI assistant that helps users interact with MongoDB databases through MCP (Model Context Protocol) servers. You can process queries, analyze data, and provide insights."
  
  idle_session_ttl_in_seconds = 1800
  
  tags = local.tags
}

# Bedrock Agent Action Group
resource "aws_bedrock_agent_action_group" "mcp_action_group" {
  agent_id          = aws_bedrock_agent.mcp_agent.id
  action_group_name = "${local.name_prefix}-action-group"
  
  action_group_executor {
    lambda {
      lambda_arn = aws_lambda_function.mcp_agent_lambda.arn
    }
  }
  
  description = "Action group for interacting with MCP servers"
  
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
                    required = ["query", "mcp_type"]
                    properties = {
                      query = {
                        type        = "string"
                        description = "The query to process"
                      }
                      mcp_type = {
                        type        = "string"
                        description = "The type of MCP to use (mongodb, mongodb_external, aws, sequential_thinking)"
                        enum        = ["mongodb", "mongodb_external", "aws", "sequential_thinking"]
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

# Bedrock Agent Alias
resource "aws_bedrock_agent_alias" "mcp_agent_alias" {
  agent_id    = aws_bedrock_agent.mcp_agent.id
  alias_name  = "${local.name_prefix}-alias"
  description = "Alias for MCP agent"
  
  routing_configuration {
    agent_version = aws_bedrock_agent_version.mcp_agent_version.agent_version
  }
  
  tags = local.tags
}

# Bedrock Agent Version
resource "aws_bedrock_agent_version" "mcp_agent_version" {
  agent_id     = aws_bedrock_agent.mcp_agent.id
  agent_version = "DRAFT"
}

# IAM Role for Bedrock Agent
resource "aws_iam_role" "bedrock_agent_role" {
  name = "${local.name_prefix}-bedrock-agent-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
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
      }
    ]
  })
}

# Lambda Function for Bedrock Agent
resource "aws_lambda_function" "mcp_agent_lambda" {
  function_name = "${local.name_prefix}-mcp-agent-lambda"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.handler"
  runtime       = "nodejs18.x"
  timeout       = 30
  
  filename      = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  
  vpc_config {
    subnet_ids         = module.vpc.private_subnets
    security_group_ids = [aws_security_group.lambda.id]
  }
  
  environment {
    variables = {
      MCP_SERVER_URL = "http://${local.name_prefix}-mcp-server.${local.name_prefix}-cluster.local:8000"
    }
  }
  
  tags = local.tags
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
const https = require('https');
const http = require('http');
const url = require('url');

exports.handler = async (event) => {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    try {
        const apiPath = event.actionGroup;
        const apiOperation = event.apiPath;
        const parameters = event.parameters || [];
        
        // Extract parameters
        const paramMap = {};
        parameters.forEach(param => {
            paramMap[param.name] = param.value;
        });
        
        // Prepare request to MCP server
        const requestBody = {
            query: paramMap.query,
            mcp_type: paramMap.mcp_type || 'mongodb',
            parameters: paramMap.parameters ? JSON.parse(paramMap.parameters) : {}
        };
        
        // Call MCP server
        const mcpServerUrl = process.env.MCP_SERVER_URL || 'http://localhost:8000';
        const response = await callMcpServer(`${mcpServerUrl}/process`, requestBody);
        
        return {
            actionGroup: apiPath,
            apiPath: apiOperation,
            response: response
        };
    } catch (error) {
        console.error('Error:', error);
        return {
            actionGroup: event.actionGroup,
            apiPath: event.apiPath,
            response: {
                status: 'error',
                message: error.message
            }
        };
    }
};

async function callMcpServer(apiUrl, body) {
    return new Promise((resolve, reject) => {
        const parsedUrl = url.parse(apiUrl);
        const options = {
            hostname: parsedUrl.hostname,
            port: parsedUrl.port,
            path: parsedUrl.path,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        const client = parsedUrl.protocol === 'https:' ? https : http;
        
        const req = client.request(options, (res) => {
            let data = '';
            
            res.on('data', (chunk) => {
                data += chunk;
            });
            
            res.on('end', () => {
                try {
                    const parsedData = JSON.parse(data);
                    resolve(parsedData);
                } catch (e) {
                    reject(new Error(`Failed to parse response: ${e.message}`));
                }
            });
        });
        
        req.on('error', (e) => {
            reject(new Error(`Request error: ${e.message}`));
        });
        
        req.write(JSON.stringify(body));
        req.end();
    });
}
EOF
    filename = "index.js"
  }
}

# Output the Bedrock Agent ID and Alias ID
output "bedrock_agent_id" {
  description = "The ID of the Bedrock Agent"
  value       = aws_bedrock_agent.mcp_agent.id
}

output "bedrock_agent_alias_id" {
  description = "The ID of the Bedrock Agent Alias"
  value       = aws_bedrock_agent_alias.mcp_agent_alias.id
}