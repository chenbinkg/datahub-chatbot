# DTIS Ontology Processing

This directory contains scripts and data for processing DTIS (Deep-sea Taxonomy Information System) ontology data, enriching it with WoRMS (World Register of Marine Species) information, and building taxonomic knowledge graphs.

## Data Files

- `biigle_labels.csv` - Raw taxonomic labels from BIIGLE with basic hierarchy
- `biigle_labels_with_ranks_filled.csv` - Enriched labels with WoRMS taxonomic ranks
- `biigle_label_tree_filled_rank.json` - Processed taxonomic lineages in JSON format

## Processing Workflow

Execute scripts in this sequence:

### 1. Enrich with WoRMS Data
```bash
python3 populate_worms_columns.py biigle_labels.csv biigle_labels_with_ranks_filled.csv
```

**Purpose**: Enriches taxonomic data by querying WoRMS API using AphiaID from `source_id` column.

**Adds columns**:
- `rank` - Taxonomic rank (Species, Genus, Family, etc.)
- `scientificname` - Scientific name from WoRMS
- `status` - Taxonomic status
- `valid_AphiaID` - Valid AphiaID reference
- `valid_name` - Valid taxonomic name
- `valid_rank` - Valid taxonomic rank

**Features**:
- Parallel API requests with retry logic
- Fills missing ranks for non-WoRMS entries as "Arbitrary"
- Auto-detects CSV delimiters

### 2. Build Taxonomic Lineages
```bash
python3 build_lineages.py biigle_labels_with_ranks_filled.csv > biigle_label_tree_filled_rank.json
```

**Purpose**: Creates bottom-to-top taxonomic lineages for leaf nodes only.

**Output format**:
```json
{
  "leaf_name": [
    {"leaf_name": {"rank": "Species", "AphiaID": "123456"}},
    {"parent_name": {"rank": "Genus", "AphiaID": "123457"}},
    {"root_name": {"rank": "Kingdom", "AphiaID": "123458"}}
  ]
}
```

**Features**:
- Deduplicates identical lineages
- Handles naming conflicts with ID suffixes
- Uses valid names/IDs when available

### 3. Load into Graph Database

#### Neo4j (Local)
```bash
python3 write_to_neo4j.py
```

**Purpose**: Creates taxonomic graph in local Neo4j instance.

**Configuration**:
- URI: `neo4j://127.0.0.1:7687`
- Database: `dtis-master`
- Creates nodes with rank labels and `BELONGS_TO` relationships


## Requirements

```bash
pip install requests neo4j boto3
```

## Configuration

- **WoRMS API**: Uses `https://www.marinespecies.org/rest` (configurable)
- **Neo4j**: Update connection details in `write_to_neo4j.py`
