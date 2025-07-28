from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseMCP(ABC):
    """Base class for all MCP implementations"""
    
    @abstractmethod
    def process(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Process a query using this MCP
        
        Args:
            query: The query string to process
            parameters: Optional parameters for the query
            
        Returns:
            The result of the query processing
        """
        pass