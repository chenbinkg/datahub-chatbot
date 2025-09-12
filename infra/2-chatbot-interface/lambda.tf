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
      },

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
  handler       = "lambda_function_mcp_agent.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  
  filename      = data.local_file.lambda_zip.filename
  source_code_hash = data.local_file.lambda_zip.content_sha256

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

# Lambda additional permissions for MCP server and Neptune access
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
      },
      # {
      #   Action = [
      #     "neptune-db:*"
      #   ]
      #   Effect   = "Allow"
      #   Resource = "${aws_neptune_cluster.taxonomy_graph.arn}/*"
      # }
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
data "local_file" "lambda_zip" {
  filename = "lambda_mcp_agent.zip"
}