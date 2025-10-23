variable "project_name" {
  type = string
  default = "datahub-mcp"
}

variable "project_id" {
  type = string
  default = "FPEI2606"
}

variable "environment" {
  type = string
  default = "dev"
}

variable "service_owner" {
  type = string
  default = "Jochen Schmidt"
}

variable "service_category" {
  type = string
  default = "llm"
}

variable "authors" {
  type = string
  default = "Bryce Chen"
}

variable "aws_region" {
  type    = string
  default = "ap-southeast-2"
}

variable "vpc_cidr" {
  type    = string
  default = "10.1.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["ap-southeast-2a", "ap-southeast-2b"]
}

variable "private_subnets" {
  type    = list(string)
  default = ["10.1.1.0/24", "10.1.2.0/24"]
}

variable "public_subnets" {
  type    = list(string)
  default = ["10.1.101.0/24", "10.1.102.0/24"]
}

variable "ssh_allowed_cidr" {
  type    = list(string)
  default = ["0.0.0.0/0"] # Restrict this in production
}

variable "ssh_key_name" {
  type    = string
  default = "mcp-server-key" # Create this key pair in AWS console
}

variable "mcp_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "task_cpu" {
  type    = string
  default = "1024" # 1 vCPU
}

variable "task_memory" {
  type    = string
  default = "2048" # 2 GB
}

variable "service_desired_count" {
  type    = number
  default = 1
}

variable "mcp_service_desired_count" {
  type    = number
  default = 1
}

variable "mcp_task_cpu" {
  type    = string
  default = "512"
}

variable "mcp_task_memory" {
  type    = string
  default = "1024"
}

variable "mongo_uri" {
  type        = string
  description = "MongoDB connection URI"
  default     = "mongodb://localhost:27017"
  sensitive   = true
}

variable "mongo_db" {
  type        = string
  description = "MongoDB database name"
  default     = "data_hub"
}

variable "sagemaker_vpc_cidr" {
  type    = string
  default = "192.168.0.0/16"
}
# Bedrock agent and alias IDs are now created by Terraform