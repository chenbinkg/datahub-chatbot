import json
from neo4j import GraphDatabase

# ---- CONFIG ----
NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "neo4j123"
NEO4J_DATABASE = "dtis-master"
JSON_FILE = "biigle_label_tree_filled_rank.json"

# ---- FUNCTIONS ----
def create_graph_from_json(json_data, driver, db_name):
    with driver.session(database=db_name) as session:
        for lineage_name, lineage_list in json_data.items():
            prev_node_id = None
            for entry in lineage_list:
                for name, details in entry.items():
                    rank = details.get("rank", "").strip() or "Unknown"
                    aphia_id = details.get("AphiaID", "").strip()

                    if aphia_id:
                        merge_query = f"""
                        MERGE (n:`{rank}` {{aphia_id: $aphia_id}})
                        SET n.name = $name
                        """
                        params = {"aphia_id": aphia_id, "name": name}
                    else:
                        merge_query = f"""
                        MERGE (n:`{rank}` {{name: $name}})
                        """
                        params = {"name": name}

                    session.run(merge_query, params)

                    curr_node_id = aphia_id or name
                    if prev_node_id and prev_node_id != curr_node_id:
                        rel_query = """
                        MATCH (a), (b)
                        WHERE (a.aphia_id = $prev_id OR a.name = $prev_id)
                          AND (b.aphia_id = $curr_id OR b.name = $curr_id)
                        MERGE (a)-[:BELONGS_TO]->(b)
                        """
                        session.run(rel_query, {"prev_id": prev_node_id, "curr_id": curr_node_id})

                    prev_node_id = curr_node_id


# ---- MAIN ----
if __name__ == "__main__":
    # Load JSON
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Connect to Neo4j
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        create_graph_from_json(data, driver, NEO4J_DATABASE)
        driver.close()
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Check Neo4j is running and credentials are correct")
    print("Graph import completed!")
