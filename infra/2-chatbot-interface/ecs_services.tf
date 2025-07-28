# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  
  tags = local.tags
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "mcp_server" {
  name              = "/ecs/${local.name_prefix}-mcp-server"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_cloudwatch_log_group" "gradio_ui" {
  name              = "/ecs/${local.name_prefix}-gradio-ui"
  retention_in_days = 30
  tags              = local.tags
}

# MCP Server Task Definition
resource "aws_ecs_task_definition" "mcp_server" {
  family                   = "${local.name_prefix}-mcp-server"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.mcp_task_cpu
  memory                   = var.mcp_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "mcp-server"
      image     = "${aws_ecr_repository.mcp_server.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        },
        {
          containerPort = 8001
          protocol      = "tcp"
        }
      ]
      environment = [
        {
          name  = "AWS_REGION"
          value = var.aws_region
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.mcp_server.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "mcp-server"
        }
      }
    }
  ])

  tags = local.tags
}

# MCP Server Service
resource "aws_ecs_service" "mcp_server" {
  name            = "${local.name_prefix}-mcp-server"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.mcp_server.arn
  desired_count   = var.mcp_service_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.mcp_server.id]
    assign_public_ip = false
  }

  tags = local.tags
}

# Gradio UI Task Definition
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
      name      = "gradio-ui"
      image     = "${aws_ecr_repository.gradio_ui.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 7860
          protocol      = "tcp"
        }
      ]
      environment = [
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

# Gradio UI Service
resource "aws_ecs_service" "gradio_ui" {
  name            = "${local.name_prefix}-gradio-ui"
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
    container_name   = "gradio-ui"
    container_port   = 7860
  }

  depends_on = [aws_lb_listener.http]

  tags = local.tags
}