import pymongo
from typing import Dict, Any, Optional, List
import json
import re
from .base_mcp import BaseMCP

class MongoDBMCP(BaseMCP):
    """
    Refactored and more readable MCP implementation for MongoDB interactions.
    This version separates query parsing from command execution and correctly handles
    MongoDB shell commands with arguments.
    """
    
    def __init__(self, mongo_uri: str, database_name: str):
        """
        Initialize MongoDB MCP with connection settings.
        
        Args:
            mongo_uri: MongoDB connection URI.
            database_name: Default database name.
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

    def process(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Process a MongoDB query string, intelligently parsing its intent
        and executing the appropriate command.
        
        Args:
            query: The query string (can be a command or natural language).
            parameters: Optional parameters to override parsed values.
                
        Returns:
            Query results or an error dictionary.
        """
        if parameters is None:
            parameters = {}
        
        try:
            # Step 1: Parse the query string to determine intent and extract parameters.
            parsed_params = self._parse_query(query)
            
            # Step 2: Merge parsed parameters with any provided by the user.
            # User-provided parameters take precedence.
            final_params = {**parsed_params, **parameters}
            
            # Step 3: Execute the command based on the final parameters.
            return self._execute_operation(final_params)

        except Exception as e:
            return {"error": f"An error occurred while processing the query: {e}"}

    def _parse_query(self, query: str) -> Dict[str, Any]:
        """
        Parses a MongoDB query string to extract a standardized dictionary of parameters.
        This method safely handles different query formats.
        
        Args:
            query: The raw query string.
            
        Returns:
            A dictionary of parsed parameters.
        """
        query_lower = query.lower().strip()
        
        # --- Pattern 1: Database-level commands (e.g., getSiblingDB, listCollections) ---
        
        # Handle getSiblingDB commands
        if 'getSiblingDB(' in query:
            db_match = re.search(r'getSiblingDB\(["\']([^"\']*)["\'\)]', query)
            if db_match:
                db_name = db_match.group(1)
                
                # Check what comes after getSiblingDB
                if 'listCollections()' in query:
                    if '.map(c => c.name)' in query or '.map(' in query:
                        return {
                            "operation": "list_collections",
                            "database": db_name,
                            "format": "names_only"
                        }
                    else:
                        return {
                            "operation": "list_collections", 
                            "database": db_name,
                            "format": "full_info"
                        }
                elif 'getCollectionNames()' in query:
                    return {
                        "operation": "list_collections",
                        "database": db_name,
                        "format": "names_only"
                    }
        
        # Handle direct database commands
        elif 'getDBNames()' in query:
            return {"operation": "list_databases"}
        
        elif 'listCollections()' in query:
            if '.map(c => c.name)' in query or '.map(' in query:
                return {"operation": "list_collections", "format": "names_only"}
            else:
                return {"operation": "list_collections", "format": "full_info"}
        
        elif 'getCollectionNames()' in query:
            return {"operation": "list_collections", "format": "names_only"}
        
        # --- Pattern 2: MongoDB Shell Command (e.g., db.coll.find({...}, {...}).limit(5)) ---
        shell_command_match = re.search(
            r'db\.([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\(([^)]*)\)', query
        )
        
        if shell_command_match:
            collection_name = shell_command_match.group(1)
            method_name = shell_command_match.group(2)
            args_str = shell_command_match.group(3)
            
            try:
                args = self._parse_json_args(args_str) if args_str.strip() else []
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON arguments from shell command: {e}")

            params = {
                "collection": collection_name,
                "operation": self._map_method_to_operation(method_name)
            }
            
            if method_name in ["find", "findOne"]:
                params["filter"] = args[0] if len(args) > 0 else {}
                if len(args) > 1:
                    params["projection"] = args[1]
                if method_name == "findOne":
                    params["limit"] = 1
                
                # Check for chained .limit() method
                limit_match = re.search(r'\.limit\((\d+)\)', query)
                if limit_match:
                    params["limit"] = int(limit_match.group(1))
            
            elif method_name in ["countDocuments", "count"]:
                params["filter"] = args[0] if len(args) > 0 else {}
            
            elif method_name == "aggregate":
                params["pipeline"] = args[0] if len(args) > 0 else []
            
            return params
            
        # --- Pattern 2: Natural Language Queries ---
        if 'list' in query_lower or 'show' in query_lower:
            if 'database' in query_lower or 'dbs' in query_lower:
                return {"operation": "list_databases"}
            if 'collection' in query_lower or 'collections' in query_lower:
                return {"operation": "list_collections"}

        if any(word in query_lower for word in ['find', 'search', 'query', 'get']):
            return {"operation": "find"}
            
        return {"operation": "list_collections"}

    def _parse_json_args(self, args_str: str) -> List[Any]:
        """
        Parses MongoDB shell syntax arguments into Python objects.
        Handles both JSON and MongoDB shell syntax (unquoted property names).
        
        Args:
            args_str: The string containing the arguments.
            
        Returns:
            A list of parsed Python objects.
        """
        if not args_str.strip():
            return []
        
        # Clean up the string - remove extra whitespace and newlines
        clean_str = re.sub(r'\s+', ' ', args_str.strip())
        
        # Convert MongoDB shell syntax to valid JSON
        # Replace MongoDB operators (e.g., $match, $group) - keep them as is
        # Replace unquoted property names with quoted ones, but preserve MongoDB operators
        json_str = re.sub(r'(\$\w+)', r'"\1"', clean_str)  # Quote MongoDB operators
        json_str = re.sub(r'(\w+)\s*:', r'"\1":', json_str)  # Quote property names
        json_str = re.sub(r'"(\$\w+)"', r'\1', json_str)  # Unquote MongoDB operators back
        
        try:
            # Try to parse as a single JSON object/array first
            return [json.loads(json_str)]
        except json.JSONDecodeError:
            # If that fails, try splitting by commas and parsing each part
            arg_list = re.split(r',\s*(?=\{)', json_str)
            return [json.loads(arg.strip()) for arg in arg_list if arg.strip()]

    def _map_method_to_operation(self, method: str) -> str:
        """Maps a MongoDB shell method name to a standardized operation name."""
        if method in ["find", "findOne"]:
            return "find"
        if method in ["insert", "insertOne", "insertMany"]:
            return "insert"
        if method in ["update", "updateOne", "updateMany"]:
            return "update"
        if method in ["delete", "deleteOne", "deleteMany"]:
            return "delete"
        if method in ["aggregate"]:
            return "aggregate"
        if method in ["countDocuments", "count"]:
            return "count"
        return "unknown"

    def _execute_operation(self, params: Dict[str, Any]) -> Any:
        """
        Executes a MongoDB command based on a standardized dictionary of parameters.
        
        Args:
            params: A dictionary with 'operation', 'collection', and other command-specific keys.
            
        Returns:
            The result of the MongoDB operation.
        """
        operation = params.get("operation")
        db_name = params.get("database", self.db_name)
        db = self.client[db_name]
        
        if operation == "list_databases":
            databases = self.client.list_database_names()
            return {"databases": databases, "count": len(databases)}
        
        if operation == "list_collections":
            collections = db.list_collection_names()
            format_type = params.get("format", "names_only")
            
            if format_type == "names_only":
                return {
                    "database": db_name,
                    "collections": collections,
                    "count": len(collections)
                }
            else:  # full_info
                collections_info = []
                for coll_name in collections:
                    collections_info.append({
                        "name": coll_name,
                        "type": "collection"
                    })
                return {
                    "database": db_name,
                    "collections": collections_info,
                    "count": len(collections_info)
                }

        collection_name = params.get("collection")
        if not collection_name:
            return {"error": f"Collection name is required for operation '{operation}'"}
        
        collection = db[collection_name]

        if operation == "find":
            filter_query = params.get("filter", {})
            projection = params.get("projection")
            limit = params.get("limit", 100)
            
            cursor = collection.find(filter_query, projection=projection)
            results = list(cursor.limit(limit))
            
            for doc in results:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
            return results
        
        if operation == "count":
            filter_query = params.get("filter", {})
            count = collection.count_documents(filter_query)
            return {"count": count}
        
        if operation == "aggregate":
            pipeline = params.get("pipeline", [])
            results = list(collection.aggregate(pipeline))
            
            for doc in results:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
            return results
        
        return {"error": f"Unsupported operation: {operation}"}