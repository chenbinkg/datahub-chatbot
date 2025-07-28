# Infrastructure Architecture

## Overview

This diagram shows the containerized architecture deployed on AWS using ECS Fargate.

```mermaid
graph TB
    %% External Services
    User[👤 User]
    MongoDB[(🍃 MongoDB Atlas)]
    
    %% AWS Services
    subgraph "AWS Account"
        subgraph "VPC"
            subgraph "Public Subnets"
                ALB[🔄 Application Load Balancer]
                NAT[🌐 NAT Gateway]
            end
            
            subgraph "Private Subnets"
                subgraph "ECS Fargate Cluster"
                    subgraph "Gradio UI Service"
                        GradioTask[📱 Gradio UI Container<br/>Port: 7860]
                    end
                    
                    subgraph "MCP Server Service"
                        MCPTask[🔧 MCP Server Container<br/>Port: 8000 & 8001<br/>- Custom MCP<br/>- MongoDB MCP<br/>- AWS MCP<br/>- Sequential Thinking MCP]
                    end
                end
                
                Lambda[⚡ Lambda Function<br/>Bedrock Agent Handler]
            end
        end
        
        %% AWS Managed Services
        Cognito[🔐 Cognito User Pool]
        BedrockAgent[🤖 Bedrock Agent]
        SSM[📋 Systems Manager<br/>Parameter Store]
        CloudWatch[📊 CloudWatch Logs]
        ECR[📦 Elastic Container Registry<br/>- MCP Server Image<br/>- Gradio UI Image]
        S3[🪣 S3 Bucket<br/>Terraform State]
    end
    
    %% External AI Services
    Bedrock[🧠 Amazon Bedrock<br/>Claude Models<br/>Cross-Region: us-east-1]
    
    %% User Flow
    User --> ALB
    ALB --> GradioTask
    
    %% Internal Communication
    GradioTask --> Cognito
    GradioTask --> BedrockAgent
    GradioTask --> SSM
    
    BedrockAgent --> Lambda
    Lambda --> MCPTask
    
    MCPTask --> MongoDB
    MCPTask --> Bedrock
    MCPTask --> SSM
    
    %% Logging
    GradioTask --> CloudWatch
    MCPTask --> CloudWatch
    Lambda --> CloudWatch
    
    %% Container Registry
    ECR --> GradioTask
    ECR --> MCPTask
    
    %% State Management
    S3 -.-> |Terraform State| VPC
    
    %% Styling
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef container fill:#0066CC,stroke:#fff,stroke-width:2px,color:#fff
    classDef external fill:#4CAF50,stroke:#fff,stroke-width:2px,color:#fff
    classDef storage fill:#8E44AD,stroke:#fff,stroke-width:2px,color:#fff
    
    class ALB,Cognito,BedrockAgent,SSM,CloudWatch,Lambda,Bedrock aws
    class GradioTask,MCPTask container
    class User,MongoDB external
    class ECR,S3 storage
```

## Component Details

### **Frontend Layer**
- **Application Load Balancer**: Routes traffic to Gradio UI containers
- **Gradio UI Container**: Web interface for user interaction

### **Application Layer**
- **MCP Server Container**: Single container running multiple MCP servers:
  - Custom MongoDB MCP (Port 8000)
  - External MongoDB MCP (Port 8001)
  - AWS MCP for service interactions
  - Sequential Thinking MCP for complex reasoning

### **AI/ML Layer**
- **Bedrock Agent**: Orchestrates AI interactions
- **Lambda Function**: Handles Bedrock agent requests
- **Amazon Bedrock**: Claude models for AI processing (cross-region)

### **Data Layer**
- **MongoDB Atlas**: External database
- **SSM Parameter Store**: Configuration management
- **S3**: Terraform state storage

### **Security & Networking**
- **VPC**: Isolated network environment
- **Private Subnets**: Application containers
- **Public Subnets**: Load balancer and NAT gateway
- **Cognito**: User authentication
- **IAM Roles**: Service permissions

### **DevOps**
- **ECR**: Container image registry
- **CloudWatch**: Centralized logging
- **ECS Fargate**: Serverless container orchestration

## Key Features

1. **Containerized Architecture**: All applications run in Docker containers
2. **Serverless Compute**: ECS Fargate eliminates server management
3. **Cross-Region AI**: Bedrock models accessible from different regions
4. **Centralized Configuration**: SSM Parameter Store for all settings
5. **Infrastructure as Code**: Terraform manages all resources
6. **Secure Networking**: Private subnets with controlled access
7. **Scalable Design**: Auto-scaling containers based on demand