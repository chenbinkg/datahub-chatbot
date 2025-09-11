import json
import os
import urllib3
import logging
import boto3
# from gremlin_python.driver import client
# from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
# from gremlin_python.process.anonymous_traversal import traversal

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize HTTP client
http = urllib3.PoolManager()

# Initialize SSM client
ssm = boto3.client('ssm')

# def handle_neptune_query(query, context):
#     """Handle Neptune graph queries for taxonomy"""
#     try:
#         # Get Neptune endpoint from SSM
#         neptune_endpoint = ssm.get_parameter(Name='/remote-mcp-server/neptune-endpoint')['Parameter']['Value']
#         neptune_port = ssm.get_parameter(Name='/remote-mcp-server/neptune-port')['Parameter']['Value']
        
#         # Connect to Neptune
#         connection = DriverRemoteConnection(f'wss://{neptune_endpoint}:{neptune_port}/gremlin', 'g')
#         g = traversal().withRemote(connection)
        
#         # Simple taxonomy queries based on query content
#         if 'parent' in query.lower() or 'ancestor' in query.lower():
#             # Find parent/ancestors of a taxon
#             taxon_name = extract_taxon_name(query)
#             result = g.V().has('name', taxon_name).out('BELONGS_TO').valueMap().toList()
#         elif 'child' in query.lower() or 'descendant' in query.lower():
#             # Find children/descendants of a taxon
#             taxon_name = extract_taxon_name(query)
#             result = g.V().has('name', taxon_name).in_('BELONGS_TO').valueMap().toList()
#         elif 'lineage' in query.lower():
#             # Get full lineage
#             taxon_name = extract_taxon_name(query)
#             result = g.V().has('name', taxon_name).repeat(__.out('BELONGS_TO')).emit().valueMap().toList()
#         else:
#             # Default: search by name
#             taxon_name = extract_taxon_name(query)
#             result = g.V().has('name', containing(taxon_name)).valueMap().toList()
        
#         connection.close()
        
#         return {
#             'messageVersion': '1.0',
#             'response': {
#                 'actionGroup': 'neptune-query',
#                 'apiPath': '/process',
#                 'httpMethod': 'POST',
#                 'httpStatusCode': 200,
#                 'responseBody': {
#                     'application/json': {
#                         'body': json.dumps({
#                             'status': 'success',
#                             'result': result,
#                             'query': query
#                         })
#                     }
#                 }
#             }
#         }
        
#     except Exception as e:
#         logger.error(f"Neptune query error: {str(e)}")
#         return {
#             'messageVersion': '1.0',
#             'response': {
#                 'actionGroup': 'neptune-query',
#                 'apiPath': '/process',
#                 'httpMethod': 'POST',
#                 'httpStatusCode': 500,
#                 'responseBody': {
#                     'application/json': {
#                         'body': json.dumps({
#                             'status': 'error',
#                             'message': str(e)
#                         })
#                     }
#                 }
#             }
#         }

# def extract_taxon_name(query):
#     """Extract taxon name from query"""
#     # Simple extraction - look for quoted names or capitalize words
#     import re
#     quoted = re.search(r'["\']([^"\']*)["\'']', query)
#     if quoted:
#         return quoted.group(1)
    
#     # Look for capitalized words (likely species names)
#     words = query.split()
#     for word in words:
#         if word[0].isupper() and len(word) > 2:
#             return word
    
#     return 'Unknown'

def lambda_handler(event, context):
    logger.info(f"Lambda invoked with event: {json.dumps(event, indent=2)}")
    
    try:
        action_group = event.get('actionGroup')
        api_path = event.get('apiPath')
        
        # Extract parameters from requestBody (Bedrock Agent format)
        request_body = event.get('requestBody', {})
        content = request_body.get('content', {})
        app_json = content.get('application/json', {})
        properties = app_json.get('properties', [])
        
        logger.info(f"Processing properties: {properties}")
        
        # Convert properties to parameter map
        param_map = {}
        for prop in properties:
            param_map[prop['name']] = prop['value']
        
        logger.info(f"Parameter map: {param_map}")
        
        # Prepare request to MCP server
        # Handle parameters - try to parse as JSON, otherwise use as string
        parameters_raw = param_map.get('parameters', '{}')
        try:
            if parameters_raw.startswith('{') and parameters_raw.endswith('}'):
                parameters = json.loads(parameters_raw)
            else:
                # If it's not JSON, treat it as a string parameter
                parameters = {'raw_parameters': parameters_raw}
        except json.JSONDecodeError:
            parameters = {'raw_parameters': parameters_raw}
        
        # Ensure mcp_type always has a value
        mcp_type = param_map.get('mcp_type')
        if not mcp_type:
            mcp_type = 'mongodb'  # Default to mongodb
            logger.info(f"No mcp_type provided, defaulting to: {mcp_type}")
        
        mcp_request = {
            'query': param_map.get('query'),
            'mcp_type': mcp_type,
            'parameters': parameters
        }
        
        logger.info(f"Final MCP request: {mcp_request}")
        
        logger.info(f"Request body for MCP server: {mcp_request}")
        
        # Validate required fields
        if not mcp_request['query']:
            raise ValueError("Query parameter is required")
        
        # # Handle Neptune graph queries
        # if mcp_request['mcp_type'] == 'neptune' or 'taxonomy' in mcp_request['query'].lower():
        #     return handle_neptune_query(mcp_request['query'], context)
        
        # Ensure mcp_type is valid
        valid_mcp_types = ['mongodb', 'mongodb_external', 'aws', 'sequential_thinking']
        if mcp_request['mcp_type'] not in valid_mcp_types:
            logger.warning(f"Invalid mcp_type: {mcp_request['mcp_type']}, defaulting to mongodb")
            mcp_request['mcp_type'] = 'mongodb'
        
        # Call MCP server
        mcp_server_url = os.environ.get('MCP_SERVER_URL', 'http://localhost:8000')
        url = f"{mcp_server_url}/process"
        
        logger.info(f"Calling MCP server at: {url}")
        
        response = http.request(
            'POST',
            url,
            body=json.dumps(mcp_request),
            headers={'Content-Type': 'application/json'}
        )
        
        logger.info(f"MCP server response status: {response.status}")
        logger.info(f"Raw MCP server response: {response.data.decode('utf-8')}")
        
        if response.status == 200:
            mcp_response = json.loads(response.data.decode('utf-8'))
        else:
            mcp_response = {
                'status': 'error',
                'message': f'MCP server returned status {response.status}',
                'details': response.data.decode('utf-8')
            }
        
        logger.info(f"MCP server parsed response: {mcp_response}")
        
        # Format response for Bedrock Agent
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': action_group,
                'apiPath': api_path,
                'httpMethod': 'POST',
                'httpStatusCode': 200,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(mcp_response)
                    }
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Lambda error: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        error_response = {
            'status': 'error',
            'message': str(e),
            'type': type(e).__name__
        }
        
        return {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': event.get('actionGroup'),
                'apiPath': event.get('apiPath'),
                'httpMethod': 'POST',
                'httpStatusCode': 500,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps(error_response)
                    }
                }
            }
        }
