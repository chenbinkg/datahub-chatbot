import pymongo
from typing import Dict, Any, Optional, List, Callable
import json
import re
from .base_mcp import BaseMCP

class EnhancedMongoDBMCP(BaseMCP):
    """Enhanced MCP implementation for MongoDB interactions with FastMCP-style patterns"""
    
    def __init__(self, mongo_uri: str, database_name: str):
        """
        Initialize Enhanced MongoDB MCP
        
        Args:
            mongo_uri: MongoDB connection URI
            database_name: Default database name
        """
        # Configure MongoDB client with SSL settings for Atlas
        self.client = pymongo.MongoClient(
            mongo_uri,
            tls=True,
            tlsAllowInvalidCertificates=True,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=20000,
            socketTimeoutMS=20000
        )
        self.db_name = database_name
        self._tools = {}  # Register tools like FastMCP
        self._register_tools()
    
    def tool(self, name: str = None, description: str = None):
        """FastMCP-style decorator for registering tools"""
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            self._tools[tool_name] = {
                'function': func,
                'description': description or func.__doc__ or f"Execute {tool_name}",
                'name': tool_name
            }
            return func
        return decorator
    
    def _register_tools(self):
        """Register all available tools"""
        
        @self.tool("list_databases", "List all available MongoDB databases")
        def list_databases() -> Dict[str, Any]:
            """List all available databases in the MongoDB instance"""
            try:
                databases = self.client.list_database_names()
                return {"databases": databases, "count": len(databases)}
            except Exception as e:
                return {"error": f"Failed to list databases: {str(e)}"}
        
        @self.tool("list_collections", "List collections in a specific database")
        def list_collections(database: str = None) -> Dict[str, Any]:
            """List all collections in the specified database"""
            try:
                db_name = database or self.db_name
                db = self.client[db_name]
                collections = db.list_collection_names()
                return {
                    "database": db_name,
                    "collections": collections, 
                    "count": len(collections)
                }
            except Exception as e:
                return {"error": f"Failed to list collections: {str(e)}"}
        
        @self.tool("find_documents", "Find documents in a collection")
        def find_documents(collection: str, database: str = None, filter: Dict = None, limit: int = 100) -> Dict[str, Any]:
            """Find documents in a MongoDB collection"""
            try:
                db_name = database or self.db_name
                db = self.client[db_name]
                coll = db[collection]
                filter_query = filter or {}
                
                results = list(coll.find(filter_query).limit(limit))
                # Convert ObjectId to string for JSON serialization
                for doc in results:
                    if "_id" in doc:
                        doc["_id"] = str(doc["_id"])
                
                return {
                    "database": db_name,
                    "collection": collection,
                    "documents": results,
                    "count": len(results)
                }
            except Exception as e:
                return {"error": f"Failed to find documents: {str(e)}"}
        
        @self.tool("aggregate_documents", "Run aggregation pipeline on a collection")
        def aggregate_documents(collection: str, pipeline: List[Dict], database: str = None) -> Dict[str, Any]:
            """Execute aggregation pipeline on a MongoDB collection"""
            try:
                db_name = database or self.db_name
                db = self.client[db_name]
                coll = db[collection]
                
                results = list(coll.aggregate(pipeline))
                # Convert ObjectId to string for JSON serialization
                for doc in results:
                    if "_id" in doc:
                        doc["_id"] = str(doc["_id"])
                
                return {
                    "database": db_name,
                    "collection": collection,
                    "results": results,
                    "count": len(results)
                }
            except Exception as e:
                return {"error": f"Failed to aggregate documents: {str(e)}"}
    
    def get_available_tools(self) -> List[Dict[str, str]]:
        """Get list of available tools with descriptions"""
        return [
            {
                "name": tool_info["name"],
                "description": tool_info["description"]
            }
            for tool_info in self._tools.values()
        ]
    
    def _parse_query_intent(self, query: str) -> Dict[str, Any]:
        """Parse query to determine intent and extract parameters"""
        query_lower = query.lower().strip()
        intent = {}
        
        # Parse MongoDB shell commands
        if 'getCollectionNames()' in query or 'listCollections' in query:
            intent['tool'] = 'list_collections'
            # Extract database name from getSiblingDB if present
            if 'getSiblingDB(' in query:
                db_match = re.search(r'getSiblingDB\(["\']([^"\']*)["\'\])', query)
                if db_match:
                    intent['database'] = db_match.group(1)
        
        elif 'getDBNames()' in query or 'listDatabases' in query:
            intent['tool'] = 'list_databases'
        
        elif 'find(' in query:
            intent['tool'] = 'find_documents'
            # Try to extract collection name
            if 'db.' in query:
                coll_match = re.search(r'db\.([a-zA-Z_][a-zA-Z0-9_]*)\.find', query)
                if coll_match:
                    intent['collection'] = coll_match.group(1)
        
        # Natural language parsing
        elif any(word in query_lower for word in ['database', 'dbs', 'db']):
            if any(word in query_lower for word in ['list', 'show', 'get', 'display']):
                intent['tool'] = 'list_databases'
        
        elif any(word in query_lower for word in ['collection', 'collections']):
            if any(word in query_lower for word in ['list', 'show', 'get', 'display']):
                intent['tool'] = 'list_collections'
        
        elif any(word in query_lower for word in ['find', 'search', 'query', 'get']):
            intent['tool'] = 'find_documents'
        
        else:
            # Default to list collections
            intent['tool'] = 'list_collections'
        
        return intent
    
    def process(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Process a MongoDB query using enhanced tool-based approach
        
        Args:
            query: The query string (can be a command or natural language)
            parameters: Optional parameters for the query
                
        Returns:
            Query results from the appropriate tool
        """
        if parameters is None:
            parameters = {}
            
        print(f"Processing MongoDB query: {query}")
        print(f"Input parameters: {parameters}")
        
        # Parse query intent if tool not explicitly specified
        if 'tool' not in parameters:
            intent = self._parse_query_intent(query)
            parameters.update(intent)
        
        # Get the tool to execute
        tool_name = parameters.get('tool', 'list_collections')
        
        if tool_name not in self._tools:
            return {
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(self._tools.keys())
            }
        
        # Execute the tool
        tool_info = self._tools[tool_name]
        tool_function = tool_info['function']
        
        try:
            # Extract function parameters from the parameters dict
            import inspect
            sig = inspect.signature(tool_function)
            func_params = {}
            
            for param_name in sig.parameters:
                if param_name in parameters:
                    func_params[param_name] = parameters[param_name]
            
            print(f"Executing tool: {tool_name} with params: {func_params}")
            result = tool_function(**func_params)
            
            return {
                "tool_used": tool_name,
                "query": query,
                **result
            }
            
        except Exception as e:
            return {
                "error": f"Tool execution failed: {str(e)}",
                "tool": tool_name,
                "query": query
            }

# Backward compatibility alias
MongoDBMCP = EnhancedMongoDBMCP