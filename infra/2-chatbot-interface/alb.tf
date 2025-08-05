# Application Load Balancer
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

# Target group for MCP server
resource "aws_lb_target_group" "mcp_server" {
  name        = "${local.name_prefix}-mcp-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    interval            = 30
    path                = "/health"
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

# Target group for MongoDB MCP server (port 8001)
resource "aws_lb_target_group" "mongodb_mcp_server" {
  name        = "${local.name_prefix}-mongo-tg"
  port        = 8001
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    interval            = 30
    path                = "/"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 5
    timeout             = 10
    matcher             = "200-499"
  }

  tags = local.tags
}

# Listener for MCP server (port 8000)
resource "aws_lb_listener" "mcp_server" {
  load_balancer_arn = aws_lb.main.arn
  port              = 8000
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mcp_server.arn
  }
}

# Listener for MongoDB MCP server (port 8001)
resource "aws_lb_listener" "mongodb_mcp_server" {
  load_balancer_arn = aws_lb.main.arn
  port              = 8001
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mongodb_mcp_server.arn
  }
}