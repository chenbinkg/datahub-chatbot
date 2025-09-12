# # Neptune Serverless Cluster for GraphRAG
# resource "aws_neptune_cluster" "taxonomy_graph" {
#   cluster_identifier                   = "${local.name_prefix}-taxonomy-graph"
#   engine                               = "neptune"
#   engine_version                       = "1.2.0.1"
#   neptune_cluster_parameter_group_name = "default.neptune1.2"
  
#   neptune_subnet_group_name = aws_neptune_subnet_group.taxonomy.name
#   vpc_security_group_ids    = [aws_security_group.neptune.id]
  
#   skip_final_snapshot = true
#   apply_immediately   = true
  
#   serverless_v2_scaling_configuration {
#     min_capacity = 2.5
#     max_capacity = 128
#   }
  
#   tags = local.tags
# }

# # Neptune Serverless Instance
# resource "aws_neptune_cluster_instance" "taxonomy_graph_instance" {
#   cluster_identifier           = aws_neptune_cluster.taxonomy_graph.cluster_identifier
#   instance_class               = "db.serverless"
#   neptune_parameter_group_name = "default.neptune1.2"
  
#   tags = local.tags
# }

# # Neptune Subnet Group
# resource "aws_neptune_subnet_group" "taxonomy" {
#   name       = "${local.name_prefix}-neptune-subnet-group"
#   subnet_ids = module.vpc.private_subnets
  
#   tags = local.tags
# }

# # Neptune Security Group
# resource "aws_security_group" "neptune" {
#   name        = "${local.name_prefix}-neptune-sg"
#   description = "Security group for Neptune cluster"
#   vpc_id      = module.vpc.vpc_id

#   ingress {
#     from_port       = 8182
#     to_port         = 8182
#     protocol        = "tcp"
#     security_groups = [aws_security_group.lambda.id]
#   }

#   ingress {
#     from_port       = 8182
#     to_port         = 8182
#     protocol        = "tcp"
#     security_groups = [aws_security_group.neptune_proxy.id]
#   }

#   tags = local.tags
# }

# # S3 Bucket for taxonomy data
# resource "aws_s3_bucket" "taxonomy_data" {
#   bucket = "${local.name_prefix}-taxonomy-data"
  
#   tags = local.tags
# }

# resource "aws_s3_bucket_versioning" "taxonomy_data" {
#   bucket = aws_s3_bucket.taxonomy_data.id
#   versioning_configuration {
#     status = "Enabled"
#   }
# }

# # SSM Parameters for Neptune
# resource "aws_ssm_parameter" "neptune_endpoint" {
#   name  = "/remote-mcp-server/neptune-endpoint"
#   type  = "String"
#   value = aws_neptune_cluster.taxonomy_graph.endpoint
  
#   tags = local.tags
# }

# resource "aws_ssm_parameter" "neptune_port" {
#   name  = "/remote-mcp-server/neptune-port"
#   type  = "String"
#   value = "8182"
  
#   tags = local.tags
# }

# # Outputs
# output "neptune_endpoint" {
#   description = "Neptune Serverless Cluster Endpoint"
#   value       = aws_neptune_cluster.taxonomy_graph.endpoint
# }

# output "neptune_cluster_arn" {
#   description = "Neptune Serverless Cluster ARN"
#   value       = aws_neptune_cluster.taxonomy_graph.arn
# }

# output "taxonomy_s3_bucket" {
#   description = "S3 bucket for taxonomy data"
#   value       = aws_s3_bucket.taxonomy_data.bucket
# }