import requests
from typing import Dict, Any, Optional
import json
import os
from .base_mcp import BaseMCP

class MongoDBExternalMCP(BaseMCP):
    """MCP implementation that proxies requests to the external MongoDB MCP server"""
    
    def __init__(self, mcp_server_url: str = None):
        """
        Initialize MongoDB External MCP
        
        Args:
            mcp_server_url: URL of the MongoDB MCP server
        """
        self.mcp_server_url = mcp_server_url or os.environ.get("MONGODB_MCP_SERVER_URL", "http://localhost:8001")
        print(f"MongoDB External MCP initialized with URL: {self.mcp_server_url}")
        
    def process(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Process a query by forwarding it to the external MongoDB MCP server
        
        Args:
            query: The query string to process
            parameters: Optional parameters for the query
            
        Returns:
            The result from the MongoDB MCP server
        """
        if parameters is None:
            parameters = {}
            
        try:
            # Prepare the request payload
            payload = {
                "query": query,
                "parameters": parameters
            }
            
            # Send the request to the MongoDB MCP server
            url = f"{self.mcp_server_url}/api/v1/process"
            print(f"Sending request to MongoDB MCP server at: {url}")
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            # Check if the request was successful
            response.raise_for_status()
            
            # Return the response data
            return response.json()
            
        except requests.exceptions.RequestException as e:
            return {"error": f"Failed to communicate with MongoDB MCP server: {str(e)}"}
        except Exception as e:
            return {"error": str(e)}