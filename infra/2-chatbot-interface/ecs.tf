# ECS Cluster for Gradio UI
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  
  tags = local.tags
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "gradio_ui" {
  name              = "/ecs/${local.name_prefix}-gradio-ui"
  retention_in_days = 30

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

# ECS Service
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
    container_name   = "gradio-ui-${var.environment}"
    container_port   = 7860
  }

  depends_on = [aws_lb_listener.http]

  tags = local.tags
}