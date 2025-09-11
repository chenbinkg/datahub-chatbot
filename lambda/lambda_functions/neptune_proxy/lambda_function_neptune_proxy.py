import json
import os
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import __

def lambda_handler(event, context):
    try:
        # Parse request
        if 'body' in event:
            body = json.loads(event['body'])
        else:
            body = event
            
        action = body.get('action', 'query')
        data = body.get('data', {})
        
        endpoint = os.environ['NEPTUNE_ENDPOINT']
        port = os.environ['NEPTUNE_PORT']
        
        if action == 'load_taxonomy':
            result = load_taxonomy_data(endpoint, port, data)
        elif action == 'clear_data':
            result = clear_taxonomy_data(endpoint, port)
        elif action == 'query':
            result = execute_query(endpoint, port, body.get('query', ''))
        elif action == 'test_connection':
            result = test_connection(endpoint, port)
        else:
            result = {'error': 'Unknown action'}
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }

def clear_taxonomy_data(endpoint, port):
    """Clear all taxonomy data from Neptune"""
    try:
        connection = DriverRemoteConnection(f'wss://{endpoint}:{port}/gremlin', 'g')
        g = traversal().withRemote(connection)
        
        # Count existing vertices
        count_before = g.V().count().next()
        
        # Clear all data
        g.V().drop().iterate()
        
        connection.close()
        return {'status': 'success', 'cleared_nodes': count_before}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def load_taxonomy_data(endpoint, port, json_data):
    """Load taxonomy data using Gremlin WebSocket connection"""
    try:
        # Connect to Neptune
        connection = DriverRemoteConnection(f'wss://{endpoint}:{port}/gremlin', 'g')
        g = traversal().withRemote(connection)
        
        count = 0
        vertex_cache = {}
        
        # Process in smaller chunks to avoid memory issues
        for lineage_name, lineage_list in json_data.items():
            prev_vertex = None
            
            for entry in lineage_list:
                for name, details in entry.items():
                    rank = details.get("rank", "").strip() or "Arbitrary"
                    aphia_id = details.get("AphiaID", "").strip()
                    
                    # Create unique key
                    key = f"{name}_{rank}_{aphia_id}"
                    
                    if key not in vertex_cache:
                        # Create vertex with batch optimization
                        try:
                            if aphia_id:
                                vertex = g.V().has('aphia_id', aphia_id).fold().coalesce(
                                    __.unfold(),
                                    __.addV('Taxon').property('aphia_id', aphia_id).property('name', name).property('rank', rank)
                                ).next()
                            else:
                                vertex = g.V().has('name', name).has('rank', rank).fold().coalesce(
                                    __.unfold(),
                                    __.addV('Taxon').property('name', name).property('rank', rank)
                                ).next()
                            
                            vertex_cache[key] = vertex
                        except Exception as vertex_error:
                            print(f"Error creating vertex {name}: {vertex_error}")
                            continue
                    
                    current_vertex = vertex_cache[key]
                    
                    # Create relationship to parent
                    if prev_vertex and current_vertex != prev_vertex:
                        try:
                            g.V(prev_vertex).addE('BELONGS_TO').to(__.V(current_vertex)).iterate()
                        except Exception as edge_error:
                            print(f"Error creating edge: {edge_error}")
                    
                    prev_vertex = current_vertex
                    count += 1
        
        connection.close()
        return {'status': 'success', 'loaded_nodes': count, 'unique_vertices': len(vertex_cache)}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def test_connection(endpoint, port):
    """Test connection to Neptune"""
    try:
        connection = DriverRemoteConnection(f'wss://{endpoint}:{port}/gremlin', 'g')
        g = traversal().withRemote(connection)
        
        # Simple test query
        count = g.V().count().next()
        
        connection.close()
        return {'status': 'success', 'message': 'Connection successful', 'vertex_count': count}
        
    except Exception as e:
        return {'status': 'error', 'message': f'Connection failed: {str(e)}'}

def execute_query(endpoint, port, query_str):
    """Execute query using Gremlin WebSocket connection"""
    try:
        connection = DriverRemoteConnection(f'wss://{endpoint}:{port}/gremlin', 'g')
        g = traversal().withRemote(connection)
        
        if 'count' in query_str.lower():
            result = g.V().count().next()
        else:
            result = g.V().limit(10).valueMap().toList()
        
        connection.close()
        return {'status': 'success', 'result': result}
            
    except Exception as e:
        return {'error': str(e)}