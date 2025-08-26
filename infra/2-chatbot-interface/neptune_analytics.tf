# Neptune Analytics Graph for GraphRAG
resource "aws_neptuneanalytics_graph" "taxonomy_graph" {
  graph_name               = "${local.name_prefix}-taxonomy-graph"
  provisioned_memory       = 128
  public_connectivity      = false
  replica_count           = 0
  deletion_protection     = false
  
  tags = local.tags
}

# S3 Bucket for Knowledge Base Documents
resource "aws_s3_bucket" "knowledge_base_documents" {
  bucket = "${local.name_prefix}-kb-documents-${random_id.bucket_suffix.hex}"
  
  tags = local.tags
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "knowledge_base_documents" {
  bucket = aws_s3_bucket.knowledge_base_documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

# IAM Role for Bedrock Knowledge Base
resource "aws_iam_role" "bedrock_kb_role" {
  name = "${local.name_prefix}-bedrock-kb-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
  
  tags = local.tags
}

# IAM Policy for Knowledge Base
resource "aws_iam_role_policy" "bedrock_kb_policy" {
  name = "${local.name_prefix}-bedrock-kb-policy"
  role = aws_iam_role.bedrock_kb_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.knowledge_base_documents.arn,
          "${aws_s3_bucket.knowledge_base_documents.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/cohere.embed-english-v3",
          "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "neptune-graph:*"
        ]
        Resource = aws_neptuneanalytics_graph.taxonomy_graph.arn
      }
    ]
  })
}

# Bedrock Knowledge Base
resource "aws_bedrockagent_knowledge_base" "taxonomy_kb" {
  name     = "${local.name_prefix}-taxonomy-kb"
  role_arn = aws_iam_role.bedrock_kb_role.arn
  
  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/cohere.embed-english-v3"
    }
  }
  
  storage_configuration {
    type = "NEPTUNE_ANALYTICS"
    neptune_analytics_configuration {
      graph_arn = aws_neptuneanalytics_graph.taxonomy_graph.arn
      field_mapping {
        metadata_field = "metadata"
        text_field     = "text"
      }
    }
  }
  
  tags = local.tags
}

# Data Source for Knowledge Base
resource "aws_bedrockagent_data_source" "taxonomy_data_source" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.taxonomy_kb.id
  name              = "${local.name_prefix}-taxonomy-data-source"
  
  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn = aws_s3_bucket.knowledge_base_documents.arn
    }
  }
  
  vector_ingestion_configuration {
    context_enrichment_configuration {
      type = "BEDROCK_FOUNDATION_MODEL"
      bedrock_foundation_model_configuration {
        model_arn = "arn:aws:bedrock:${data.aws_region.current.name}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
        enrichment_strategy_configuration {
          method = "CHUNK_ENTITY_EXTRACTION"
        }
      }
    }
  }
}

# SSM Parameters for Knowledge Base
resource "aws_ssm_parameter" "kb_id" {
  name  = "/remote-mcp-server/knowledge-base-id"
  type  = "String"
  value = aws_bedrockagent_knowledge_base.taxonomy_kb.id
  
  tags = local.tags
}

resource "aws_ssm_parameter" "kb_s3_bucket" {
  name  = "/remote-mcp-server/knowledge-base-s3-bucket"
  type  = "String"
  value = aws_s3_bucket.knowledge_base_documents.bucket
  
  tags = local.tags
}

# Outputs
output "knowledge_base_id" {
  description = "Bedrock Knowledge Base ID"
  value       = aws_bedrockagent_knowledge_base.taxonomy_kb.id
}

output "knowledge_base_s3_bucket" {
  description = "S3 bucket for knowledge base documents"
  value       = aws_s3_bucket.knowledge_base_documents.bucket
}

output "neptune_analytics_graph_arn" {
  description = "Neptune Analytics Graph ARN"
  value       = aws_neptuneanalytics_graph.taxonomy_graph.arn
}