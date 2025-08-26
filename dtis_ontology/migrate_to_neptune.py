import json
import boto3
from gremlin_python.driver import client
from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import T

# Neptune configuration
NEPTUNE_ENDPOINT = "your-neptune-cluster.cluster-xyz.us-east-1.neptune.amazonaws.com"
NEPTUNE_PORT = 8182
JSON_FILE = "biigle_label_tree_filled_rank.json"

def create_neptune_graph(json_data):
    """Create taxonomy graph in Neptune using Gremlin"""
    
    # Connect to Neptune
    connection = DriverRemoteConnection(f'wss://{NEPTUNE_ENDPOINT}:{NEPTUNE_PORT}/gremlin', 'g')
    g = traversal().withRemote(connection)
    
    try:
        # Clear existing data (optional)
        g.V().drop().iterate()
        
        for lineage_name, lineage_list in json_data.items():
            prev_vertex = None
            
            for entry in lineage_list:
                for name, details in entry.items():
                    rank = details.get("rank", "").strip() or "Unknown"
                    aphia_id = details.get("AphiaID", "").strip()
                    
                    # Create vertex with properties
                    vertex_props = {'name': name, 'rank': rank}
                    if aphia_id:
                        vertex_props['aphia_id'] = aphia_id
                    
                    # Check if vertex exists
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
                    
                    # Create relationship to parent
                    if prev_vertex:
                        g.V(prev_vertex).addE('BELONGS_TO').to(__.V(vertex)).iterate()
                    
                    prev_vertex = vertex
                    
    finally:
        connection.close()

if __name__ == "__main__":
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    create_neptune_graph(data)
    print("Neptune graph creation completed!")