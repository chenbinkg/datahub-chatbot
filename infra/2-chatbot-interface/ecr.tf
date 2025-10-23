resource "aws_ecr_repository" "mcp_server" {
  name                 = "${local.name_prefix}-mcp-server"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

# ECR Repository for Gradio UI (keep existing)
resource "aws_ecr_repository" "gradio_ui" {
  name                 = "${local.name_prefix}-gradio-ui"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}