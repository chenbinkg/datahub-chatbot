# Infrastructure Architecture

## Overview

This diagram shows the containerized architecture deployed on AWS using ECS Fargate.

```mermaid
graph TB
    %% External Services
    User[👤 User]
    MongoDB[(🍃 MongoDB Atlas)]
    LocalDev[💻 Local Development<br/>Taxonomy Data Upload]
    
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
                
                Lambda[⚡ Lambda Function<br/>Bedrock Agent Handler<br/>+ Neptune Graph Queries]
                NeptuneProxy[🌐 Neptune Proxy Lambda<br/>Public Function URL<br/>Graph Data Ingestion]
                Neptune[(🔗 Neptune Serverless<br/>Taxonomy Graph Database<br/>Gremlin Queries)]
            end
        end
        
        %% AWS Managed Services
        Cognito[🔐 Cognito User Pool]
        BedrockAgent[🤖 Bedrock Agent<br/>GraphRAG Capabilities]
        SSM[📋 Systems Manager<br/>Parameter Store<br/>+ Neptune Config]
        CloudWatch[📊 CloudWatch Logs]
        ECR[📦 Elastic Container Registry<br/>- MCP Server Image<br/>- Gradio UI Image]
        S3[🪣 S3 Bucket<br/>Terraform State<br/>+ Taxonomy Data]
    end
    
    %% External AI Services
    Bedrock[🧠 Amazon Bedrock<br/>Claude Models<br/>Cross-Region: us-east-1]
    
    %% User Flow
    User --> ALB
    ALB --> GradioTask
    
    %% Taxonomy Data Upload Flow
    LocalDev --> NeptuneProxy
    NeptuneProxy --> Neptune
    
    %% Internal Communication
    GradioTask --> Cognito
    GradioTask --> BedrockAgent
    GradioTask --> SSM
    
    BedrockAgent --> Lambda
    Lambda --> MCPTask
    Lambda --> Neptune
    
    MCPTask --> MongoDB
    MCPTask --> Bedrock
    MCPTask --> SSM
    
    %% GraphRAG Flow
    BedrockAgent -.-> |Taxonomy Queries| Neptune
    
    %% Logging
    GradioTask --> CloudWatch
    MCPTask --> CloudWatch
    Lambda --> CloudWatch
    NeptuneProxy --> CloudWatch
    
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
    
    class ALB,Cognito,BedrockAgent,SSM,CloudWatch,Lambda,Bedrock,Neptune,NeptuneProxy aws
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
- **Bedrock Agent**: Orchestrates AI interactions with GraphRAG capabilities
- **Lambda Function**: Handles Bedrock agent requests + Neptune graph queries
- **Amazon Bedrock**: Claude models for AI processing (cross-region)
- **Neptune Serverless**: Graph database for taxonomy relationships
- **Neptune Proxy Lambda**: Public endpoint for graph data ingestion

### **Data Layer**
- **MongoDB Atlas**: External database for DTIS observations
- **Neptune Serverless**: Graph database for taxonomy hierarchy
- **SSM Parameter Store**: Configuration management + Neptune endpoints
- **S3**: Terraform state storage + taxonomy data

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
3. **GraphRAG Integration**: Neptune Serverless for taxonomy knowledge graphs
4. **Cross-Region AI**: Bedrock models accessible from different regions
5. **Hybrid Data Access**: MongoDB for observations + Neptune for taxonomy
6. **External Data Ingestion**: Public Lambda proxy for graph data upload
7. **Centralized Configuration**: SSM Parameter Store for all settings
8. **Infrastructure as Code**: Terraform manages all resources
9. **Secure Networking**: Private subnets with controlled access
10. **Scalable Design**: Auto-scaling containers based on demand

## GraphRAG Workflow

1. **Data Upload**: Local machine uploads taxonomy JSON via Neptune Proxy Lambda
2. **Graph Building**: Proxy Lambda creates nodes and relationships in Neptune
3. **Query Processing**: Bedrock Agent automatically routes taxonomy queries to Neptune
4. **Graph Traversal**: Lambda executes Gremlin queries for parent/child relationships
5. **Response Generation**: Agent combines graph data with AI responses