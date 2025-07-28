from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import pymongo
import os
import boto3
from mcp.mongodb_mcp import MongoDBMCP
from mcp.mongodb_external_mcp import MongoDBExternalMCP
from mcp.aws_mcp import AWSMCP
from mcp.sequential_thinking_mcp import SequentialThinkingMCP

# Function to get parameters from SSM
def get_ssm_parameter(name, default_value=None):
    try:
        ssm_client = boto3.client('ssm', region_name=os.environ.get('AWS_REGION', 'ap-southeast-2'))
        response = ssm_client.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        print(f"Error getting SSM parameter {name}: {str(e)}")
        return default_value

# Get configuration from SSM Parameter Store
AWS_REGION = get_ssm_parameter('/remote-mcp-server/aws-region', 'ap-southeast-2')
MONGO_URI = get_ssm_parameter('/remote-mcp-server/mongo-uri', 'mongodb://localhost:27017')
MONGO_DB = get_ssm_parameter('/remote-mcp-server/mongo-db', 'data_platform')
MONGODB_MCP_SERVER_URL = get_ssm_parameter('/remote-mcp-server/mongodb-mcp-server-url', 'http://localhost:8001')

# Initialize FastAPI app
app = FastAPI(title="Remote MCP Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MCP servers
mongodb_mcp = MongoDBMCP(MONGO_URI, MONGO_DB)  # Our custom implementation
mongodb_external_mcp = MongoDBExternalMCP(MONGODB_MCP_SERVER_URL)  # External MongoDB MCP server
aws_mcp = AWSMCP()
sequential_thinking_mcp = SequentialThinkingMCP()

# Request models
class MCPRequest(BaseModel):
    query: str
    mcp_type: str = "mongodb"  # Default to MongoDB MCP
    parameters: Optional[Dict[str, Any]] = None

# Response models
class MCPResponse(BaseModel):
    result: Any
    status: str = "success"
    message: str = ""

@app.get("/")
async def root():
    return {"message": "Remote MCP Server is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/process", response_model=MCPResponse)
async def process_query(request: MCPRequest):
    try:
        # Select the appropriate MCP based on the request
        if request.mcp_type == "mongodb":
            result = mongodb_mcp.process(request.query, request.parameters)
        elif request.mcp_type == "mongodb_external":
            result = mongodb_external_mcp.process(request.query, request.parameters)
        elif request.mcp_type == "aws":
            result = aws_mcp.process(request.query, request.parameters)
        elif request.mcp_type == "sequential_thinking":
            result = sequential_thinking_mcp.process(request.query, request.parameters)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown MCP type: {request.mcp_type}")
        
        return MCPResponse(result=result)
    except Exception as e:
        return MCPResponse(
            result=None,
            status="error",
            message=str(e)
        )

@app.get("/mcp/types")
async def get_mcp_types():
    return {
        "mcp_types": [
            {"id": "mongodb", "name": "MongoDB MCP", "description": "Process MongoDB queries (custom implementation)"},
            {"id": "mongodb_external", "name": "External MongoDB MCP", "description": "Process MongoDB queries using the official MongoDB MCP server"},
            {"id": "aws", "name": "AWS MCP", "description": "Process AWS service interactions"},
            {"id": "sequential_thinking", "name": "Sequential Thinking MCP", "description": "Process complex reasoning tasks"}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)