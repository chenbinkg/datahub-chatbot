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
        self.client = pymongo.MongoClient(mongo_uri)
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
            
        # Get database and collection
        db_name = parameters.get("database", self.db_name)
        collection_name = parameters.get("collection")
        
        if not collection_name:
            return {"error": "Collection name is required"}
            
        db = self.client[db_name]
        collection = db[collection_name]
        
        # Determine operation type
        operation = parameters.get("operation", "find")
        
        try:
            if operation == "find":
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