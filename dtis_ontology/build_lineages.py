#!/usr/bin/env python3
"""
Build bottom->top unique lineages from biigle_labels_with_ranks.csv.

Top-level mapping:
    <leaf_display_name>: [
        { <leaf_display_name>: {"rank": <rank>, "AphiaID": <valid_AphiaID or source_id>} },
        { <parent_name>:       {"rank": <rank>, "AphiaID": <valid_AphiaID or source_id>} },
        ...
        { <root_name>:         {"rank": <rank>, "AphiaID": <valid_AphiaID or source_id>} }
    ]

Rules:
- Leaf display name = valid_name if non-empty, else name.
- For every node (leaf and ancestors), the entry’s "AphiaID" = valid_AphiaID if non-empty, else source_id.
- Only leaves are emitted (so no subset chains).
- Deduplicate by lineage content (same sequence of (name, rank, AphiaID)).
- If two different lineages would share the same leaf key, the later key becomes: "<leaf_name> (id:<leaf_id>)".

Usage:
    python build_lineages.py path/to/biigle_labels_with_ranks.csv > lineages.json
    e.g. python3 build_lineages.py biigle_labels_with_ranks_filled.csv > biigle_label_tree_filled_rank.json
"""

import csv
import io
import json
import sys
from collections import defaultdict
from typing import Dict, List, Tuple, Any


# ------------------------------ CSV I/O ------------------------------------- #

def load_rows(csv_path: str):
    """
    Read rows from CSV/TSV with delimiter auto-detection among ,  \t  ;  |.
    Returns (rows, detected_dialect).
    """
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()

    sample = raw[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.get_dialect("excel")

    reader = csv.DictReader(io.StringIO(raw), dialect=dialect)
    rows: List[Dict[str, str]] = []
    for r in reader:
        row = { (k.strip() if k else k): (v.strip() if v is not None else "")
                for k, v in r.items() }
        rows.append(row)
    return rows, dialect


# --------------------------- Graph & lineage logic -------------------------- #

def build_indices(rows: List[Dict[str, str]]) -> Tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, List[str]]
]:
    """
    Build two indices:
      nodes[id] = {
        'id','name','parent','rank','source_id','valid_AphiaID','valid_name'
      }
      children[parent_id] = [child_id, ...]
    """
    nodes: Dict[str, Dict[str, Any]] = {}
    children: Dict[str, List[str]] = defaultdict(list)

    for r in rows:
        nid = (r.get("id") or "").strip()
        if not nid:
            continue
        parent = (r.get("parent_id") or "").strip() or None
        rank_raw = (r.get("rank") or "").strip()
        nodes[nid] = {
            "id": nid,
            "name": (r.get("name") or "").strip(),
            "parent": parent,
            "rank": rank_raw,
            "source_id": (r.get("source_id") or "").strip(),
            "valid_AphiaID": (r.get("valid_AphiaID") or "").strip(),
            "valid_name": (r.get("valid_name") or "").strip(),
            "valid_rank": (r.get("valid_rank") or "").strip(),
        }
        if parent:
            children[parent].append(nid)

    return nodes, children


def node_valid_name_id(node: Dict[str, Any]) -> str:
    """
    Determine valid name and id for a node.
    - For leaves: use valid_name and valid_AphiaID.
    - For ancestors: use valid_name and valid_AphiaID.
    """

    return (
        node["valid_name"] if node["valid_name"] else node["name"],
        node["valid_AphiaID"] if node["valid_AphiaID"] else node["source_id"]
            )


def compute_lineage_for_leaf(leaf_id: str,
                             nodes: Dict[str, Dict[str, Any]]) -> Tuple[str, List[Dict[str, Dict[str, str]]]]:
    """
    Build the bottom->top lineage list for a leaf.

    Returns:
      (leaf_key_string, lineage_list)

    lineage_list is a list of one-key dicts like:
      [{ "<node_name>": {"rank":"...", "AphiaID":"..."} }, ...] bottom->top
    """
    if leaf_id not in nodes:
        return "", []

    # Build the chain of node ids from leaf upwards
    chain_ids: List[str] = []
    seen = set()
    current = leaf_id
    while current:
        if current in seen:
            raise ValueError(f"Cycle detected involving id={current}")
        seen.add(current)
        chain_ids.append(current)
        parent = nodes[current].get("parent")
        current = parent

    # Construct the lineage list (bottom->top) with deduplication
    lineage: List[Dict[str, Dict[str, str]]] = []
    seen_entries = set()
    
    for idx, nid in enumerate(chain_ids):
        node = nodes[nid]
        valid_name, valid_id = node_valid_name_id(node)
        
        # Create a unique key for this entry
        entry_key = (valid_name, node.get("valid_rank", ""), valid_id)
        
        # Skip if we've already seen this exact entry
        if entry_key in seen_entries:
            continue
            
        seen_entries.add(entry_key)
        lineage.append({
            valid_name: {
                "rank": node.get("valid_rank", ""),
                "AphiaID": valid_id,
            }
        })

    # Leaf key (root mapping key) is leaf display name
    leaf_display_name = list(lineage[0].keys())[0] if lineage else ""
    return leaf_display_name, lineage


def lineage_key(lineage: List[Dict[str, Dict[str, str]]]) -> Tuple:
    """
    Produce a hashable key representing lineage content:
    ((name, rank, AphiaID), (name, rank, AphiaID), ...)
    """
    out = []
    for d in lineage:
        # d is a one-key dict: {name: {rank:..., AphiaID:...}}
        if not d:
            out.append(("__empty__", "", ""))
            continue
        name = next(iter(d.keys()))
        meta = d[name] or {}
        out.append((name, meta.get("rank", ""), meta.get("AphiaID", "")))
    return tuple(out)


def build_bottom_to_top_map(rows: List[Dict[str, str]]) -> Dict[str, List[Dict[str, Dict[str, str]]]]:
    """
    Return:
      { <leaf_display_name>: [ {<name>: {"rank","AphiaID"}}, ... bottom->top ], ... }
    Only leaves are emitted; lineages are deduplicated by content.
    """
    nodes, children = build_indices(rows)

    # Leaves: nodes that never appear as parent
    leaves = [nid for nid in nodes.keys() if nid not in children]

    # Prepare candidate mapping
    temp_map: Dict[str, List[Dict[str, Dict[str, str]]]] = {}
    for leaf_id in leaves:
        leaf_key, lineage = compute_lineage_for_leaf(leaf_id, nodes)
        if not leaf_key:
            # Fallback if leaf has no usable name
            leaf_key = f"id:{leaf_id}"
        # If key already exists but lineage differs, disambiguate by id
        if leaf_key in temp_map and lineage_key(temp_map[leaf_key]) != lineage_key(lineage):
            leaf_key = f"{leaf_key} (id:{leaf_id})"
        temp_map[leaf_key] = lineage

    # Deduplicate by lineage content
    seen = set()
    out: Dict[str, List[Dict[str, Dict[str, str]]]] = {}
    for k, v in temp_map.items():
        sig = lineage_key(v)
        if sig in seen:
            continue
        seen.add(sig)
        out[k] = v

    return out


# --------------------------------- CLI -------------------------------------- #

def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("Usage: python build_lineages.py path/to/biigle_labels_with_ranks.csv", file=sys.stderr)
        return 2

    csv_path = argv[1]
    rows, _ = load_rows(csv_path)
    mapping = build_bottom_to_top_map(rows)

    print(json.dumps(mapping, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
