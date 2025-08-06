import pymongo
from typing import Dict, Any, Optional, List
import json
from .base_mcp import BaseMCP

class MongoDBMCP(BaseMCP):
    """MCP implementation for MongoDB interactions"""
    
    def __init__(self, mongo_uri: str, database_name: str):
        """
        Initialize MongoDB MCP
        
        Args:
            mongo_uri: MongoDB connection URI
            database_name: Default database name
        """
        # Configure MongoDB client with SSL settings for Atlas
        self.client = pymongo.MongoClient(
            mongo_uri,
            tls=True,
            tlsAllowInvalidCertificates=True,  # Allow self-signed certificates
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=20000,
            socketTimeoutMS=20000
        )
        self.db_name = database_name
        
    def process(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        """
        Process a MongoDB query
        
        Args:
            query: The query string (can be a command or natural language)
            parameters: Optional parameters including:
                - collection: MongoDB collection name
                - database: MongoDB database name (overrides default)
                - operation: One of 'find', 'insert', 'update', 'delete', 'aggregate'
                - filter: Query filter for find/update/delete operations
                - update: Update document for update operations
                - document: Document for insert operations
                - pipeline: Aggregation pipeline for aggregate operations
                
        Returns:
            Query results
        """
        if parameters is None:
            parameters = {}
            
        # Intelligent query parsing based on intent
        query_lower = query.lower().strip()
        
        # Parse MongoDB shell commands
        if 'operation' not in parameters:
            # Check for specific MongoDB shell commands
            if 'getCollectionNames()' in query or 'listCollections' in query:
                parameters['operation'] = 'list'
                parameters['list_type'] = 'collections'
                # Extract database name from getSiblingDB if present
                if 'getSiblingDB(' in query:
                    import re
                    db_match = re.search(r'getSiblingDB\(["\']([^"\']*)["\'\])', query)
                    if db_match:
                        parameters['database'] = db_match.group(1)
            elif 'getDBNames()' in query or 'listDatabases' in query:
                parameters['operation'] = 'list'
                parameters['list_type'] = 'databases'
            elif 'find(' in query:
                parameters['operation'] = 'find'
                # Try to extract collection name
                if 'db.' in query:
                    import re
                    coll_match = re.search(r'db\.([a-zA-Z_][a-zA-Z0-9_]*)\.find', query)
                    if coll_match:
                        parameters['collection'] = coll_match.group(1)
            # Fallback to natural language parsing
            elif any(word in query_lower for word in ['database', 'dbs', 'db']):
                if any(word in query_lower for word in ['list', 'show', 'get', 'display']):
                    parameters['operation'] = 'list'
                    parameters['list_type'] = 'databases'
            elif any(word in query_lower for word in ['collection', 'collections']):
                if any(word in query_lower for word in ['list', 'show', 'get', 'display']):
                    parameters['operation'] = 'list'
                    parameters['list_type'] = 'collections'
            elif any(word in query_lower for word in ['find', 'search', 'query', 'get']):
                parameters['operation'] = 'find'
            else:
                # Default to list collections if no clear intent
                parameters['operation'] = 'list'
                parameters['list_type'] = 'collections'
            
        # Get database (use extracted database from query if available)
        db_name = parameters.get("database", self.db_name)
        collection_name = parameters.get("collection")
        
        print(f"Processing MongoDB query: {query}")
        print(f"Parsed parameters: {parameters}")
        print(f"Using database: {db_name}, collection: {collection_name}")
        
        # Debug: Test the parsing logic
        if 'getSiblingDB(' in query:
            print(f"Found getSiblingDB in query: {query}")
            import re
            db_match = re.search(r'getSiblingDB\(["\']([^"\']*)["\'\])', query)
            if db_match:
                print(f"Extracted database name: {db_match.group(1)}")
            else:
                print("Failed to extract database name from getSiblingDB")
        
        db = self.client[db_name]
        
        # Handle collection-less operations (like listing collections)
        if not collection_name:
            operation = parameters.get("operation", "list")
            if operation == "list":
                list_type = parameters.get("list_type", "collections")
                if list_type == "collections":
                    collections = db.list_collection_names()
                    return {"collections": collections}
                elif list_type == "databases":
                    databases = self.client.list_database_names()
                    return {"databases": databases}
                else:
                    return {"error": f"Unsupported list_type: {list_type}. Use 'collections' or 'databases'"}
            else:
                return {"error": "Collection name is required for this operation"}
        
        collection = db[collection_name]
        
        # Determine operation type
        operation = parameters.get("operation", "find")
        
        try:
            if operation == "list":
                # List collections or databases
                list_type = parameters.get("list_type", "collections")
                if list_type == "collections":
                    collections = db.list_collection_names()
                    return {"collections": collections}
                elif list_type == "databases":
                    databases = self.client.list_database_names()
                    return {"databases": databases}
                else:
                    return {"error": f"Unsupported list_type: {list_type}. Use 'collections' or 'databases'"}
                    
            elif operation == "find":
                filter_query = parameters.get("filter", {})
                limit = parameters.get("limit", 100)
                results = list(collection.find(filter_query).limit(limit))
                # Convert ObjectId to string for JSON serialization
                for doc in results:
                    if "_id" in doc:
                        doc["_id"] = str(doc["_id"])
                return results
                
            elif operation == "insert":
                document = parameters.get("document", {})
                if isinstance(document, list):
                    result = collection.insert_many(document)
                    return {"inserted_ids": [str(id) for id in result.inserted_ids]}
                else:
                    result = collection.insert_one(document)
                    return {"inserted_id": str(result.inserted_id)}
                    
            elif operation == "update":
                filter_query = parameters.get("filter", {})
                update_doc = parameters.get("update", {})
                many = parameters.get("many", False)
                
                if many:
                    result = collection.update_many(filter_query, update_doc)
                    return {"matched_count": result.matched_count, "modified_count": result.modified_count}
                else:
                    result = collection.update_one(filter_query, update_doc)
                    return {"matched_count": result.matched_count, "modified_count": result.modified_count}
                    
            elif operation == "delete":
                filter_query = parameters.get("filter", {})
                many = parameters.get("many", False)
                
                if many:
                    result = collection.delete_many(filter_query)
                    return {"deleted_count": result.deleted_count}
                else:
                    result = collection.delete_one(filter_query)
                    return {"deleted_count": result.deleted_count}
                    
            elif operation == "aggregate":
                pipeline = parameters.get("pipeline", [])
                results = list(collection.aggregate(pipeline))
                # Convert ObjectId to string for JSON serialization
                for doc in results:
                    if "_id" in doc:
                        doc["_id"] = str(doc["_id"])
                return results
                
            else:
                return {"error": f"Unsupported operation: {operation}"}
                
        except Exception as e:
            return {"error": str(e)}