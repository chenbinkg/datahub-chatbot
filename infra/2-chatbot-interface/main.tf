locals {
  tags = {
    creation_method  = "terraform"
    Authors       = var.authors
    ServiceOwner = var.service_owner
    ServiceCategory = var.service_category
    Project = var.project_id
    ProjectName = var.project_name
    Environment = var.environment
  }
  name_prefix = "${var.project_name}-${var.environment}"
}

provider "aws" {
  region = var.aws_region
}

# Security Groups
resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Security group for ALB"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "ecs" {
  name        = "${local.name_prefix}-ecs-sg"
  description = "Security group for ECS tasks"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 7860
    to_port         = 7860
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "ec2_mcp" {
  name        = "${local.name_prefix}-ec2-mcp-sg"
  description = "Security group for EC2 MCP server"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidr
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

# Cognito User Pool for Authentication
resource "aws_cognito_user_pool" "main" {
  name = "${local.name_prefix}-user-pool"
  
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }
  
  tags = local.tags
}

resource "aws_cognito_user_pool_client" "client" {
  name                = "${local.name_prefix}-client"
  user_pool_id        = aws_cognito_user_pool.main.id
  generate_secret     = true
  explicit_auth_flows = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${local.name_prefix}-auth"
  user_pool_id = aws_cognito_user_pool.main.id
}

# EC2 Instance for MCP Server
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

resource "aws_instance" "mcp_server" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.mcp_instance_type
  key_name               = var.ssh_key_name
  vpc_security_group_ids = [aws_security_group.ec2_mcp.id]
  subnet_id              = module.vpc.private_subnets[0]
  iam_instance_profile   = aws_iam_instance_profile.mcp_profile.name

  user_data = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y docker git python3 python3-pip
    systemctl start docker
    systemctl enable docker
    pip3 install pymongo boto3 fastapi uvicorn
    
    # Clone the repository
    git clone https://github.com/username/remote-mcp-server.git /opt/remote-mcp-server
    
    # Start the MCP server
    cd /opt/remote-mcp-server
    python3 -m pip install -r requirements.txt
    nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /var/log/mcp-server.log 2>&1 &
  EOF

  tags = merge(local.tags, {
    Name = "${local.name_prefix}-mcp-server"
  })
}

# IAM Role for MCP Server
resource "aws_iam_role" "mcp_role" {
  name = "${local.name_prefix}-mcp-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      },
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "bedrock_access" {
  role       = aws_iam_role.mcp_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}

resource "aws_iam_instance_profile" "mcp_profile" {
  name = "${local.name_prefix}-mcp-profile"
  role = aws_iam_role.mcp_role.name
}

# ECS Cluster for Gradio UI
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  
  tags = local.tags
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.name_prefix}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      },
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM Role for ECS Task
resource "aws_iam_role" "ecs_task" {
  name = "${local.name_prefix}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      },
    ]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "bedrock_access_ecs" {
  name = "${local.name_prefix}-bedrock-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "bedrock:*",
        ]
        Effect   = "Allow"
        Resource = "*"
      },
    ]
  })
}

# ECR Repository for Gradio UI
resource "aws_ecr_repository" "gradio_ui" {
  name                 = "${local.name_prefix}-gradio-ui"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

# ECS Task Definition
resource "aws_ecs_task_definition" "gradio_ui" {
  family                   = "${local.name_prefix}-gradio-ui"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "gradio-ui-${var.environment}"
      image     = "${aws_ecr_repository.gradio_ui.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 7860
          hostPort      = 7860
          protocol      = "tcp"
        }
      ]
      environment = [
        {
          name  = "MCP_SERVER_URL"
          value = "http://${aws_instance.mcp_server.private_ip}:8000"
        },
        {
          name  = "COGNITO_USER_POOL_ID"
          value = aws_cognito_user_pool.main.id
        },
        {
          name  = "COGNITO_CLIENT_ID"
          value = aws_cognito_user_pool_client.client.id
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.gradio_ui.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "gradio-ui"
        }
      }
    }
  ])

  tags = local.tags
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "gradio_ui" {
  name              = "/ecs/${local.name_prefix}-gradio-ui"
  retention_in_days = 30

  tags = local.tags
}

# ALB
resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets

  enable_deletion_protection = var.environment == "prod"

  tags = local.tags
}

resource "aws_lb_target_group" "gradio_ui" {
  name        = "${local.name_prefix}-tg"
  port        = 7860
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    interval            = 30
    path                = "/"
    port                = "traffic-port"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    matcher             = "200-299"
  }

  tags = local.tags
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.gradio_ui.arn
  }
}

# ECS Service
resource "aws_ecs_service" "gradio_ui" {
  name            = "${local.name_prefix}-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.gradio_ui.arn
  desired_count   = var.service_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.gradio_ui.arn
    container_name   = "gradio-ui-${var.environment}"
    container_port   = 7860
  }

  depends_on = [aws_lb_listener.http]

  tags = local.tags
}
