import boto3
import os
from typing import Dict, Any, Optional
from .base_mcp import BaseMCP

class AWSMCP(BaseMCP):
    """MCP implementation for AWS service interactions"""
    
    def __init__(self):
        """Initialize AWS MCP"""
        self.default_region = os.environ.get("AWS_REGION", "ap-southeast-2")
        self.clients = {}
        
    def process(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Process an AWS service query
        
        Args:
            query: The query string
            parameters: Optional parameters including:
                - service: AWS service name (e.g., 's3', 'dynamodb')
                - operation: Service operation to perform
                - region: AWS region
                - args: Arguments for the operation
                
        Returns:
            AWS service operation results
        """
        if parameters is None:
            parameters = {}
            
        service = parameters.get("service")
        operation = parameters.get("operation")
        region = parameters.get("region", self.default_region)
        args = parameters.get("args", {})
        
        if not service or not operation:
            return {"error": "Service and operation are required"}
            
        try:
            # Get or create AWS service client for the specified region
            client_key = f"{service}:{region}"
            if client_key not in self.clients:
                self.clients[client_key] = boto3.client(service, region_name=region)
            
            client = self.clients[client_key]
            
            # Get the operation method
            operation_method = getattr(client, operation, None)
            
            if not operation_method:
                return {"error": f"Operation {operation} not found for service {service}"}
                
            # Execute the operation
            response = operation_method(**args)
            
            # Clean the response for JSON serialization
            return self._clean_response(response)
            
        except Exception as e:
            return {"error": str(e)}
            
    def _clean_response(self, response):
        """Clean AWS response for JSON serialization"""
        if isinstance(response, dict):
            clean_dict = {}
            for k, v in response.items():
                if k == "ResponseMetadata":
                    continue
                clean_dict[k] = self._clean_response(v)
            return clean_dict
        elif isinstance(response, list):
            return [self._clean_response(item) for item in response]
        elif hasattr(response, "isoformat"):  # datetime object
            return response.isoformat()
        else:
            return response