#!/usr/bin/env python3
"""
Populate WoRMS (Aphia) fields into a CSV based on source_id (AphiaID).

Adds 5 columns:
  - rank
  - scientificname
  - status
  - valid_AphiaID
  - valid_name

Rows with empty/invalid source_id keep these columns blank.

Additional behavior:
  - After WoRMS enrichment, fill missing taxonomic ranks iteratively from
    ancestors using the hierarchy [Species, Genus, Family, Order, Class, Phylum].
    The fill runs in rounds (multi-pass):
      * If a row (child) has an empty rank, and an ancestor has a non-empty rank,
        infer the child's rank as the immediate lower (more specific) rank.
      * Example: ancestor=Genus => child=Species; ancestor=Family => child=Genus.
      * This proceeds recursively: parents can be filled in one round and then
        their children in subsequent rounds.
      * We only attempt to fill rows that have **no source_id** (to avoid
        overriding authoritative WoRMS records) and whose **rank is empty**.

Usage:
    python populate_worms_columns.py input.csv output.csv \
        --base-url https://www.marinespecies.org/rest \
        --workers 5
    e.g. python3 populate_worms_columns.py biigle_labels.csv biigle_labels_with_ranks_filled.csv
"""

import argparse
import csv
import io
import sys
from typing import Dict, List, Tuple, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed


# ----------------------------- HTTP utilities -------------------------------- #

def make_session(total_retries: int = 5, backoff_factor: float = 0.5, timeout: int = 15) -> requests.Session:
    """Create a requests.Session with retry/backoff on transient errors."""
    retry = Retry(
        total=total_retries,
        read=total_retries,
        connect=total_retries,
        status=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.request_timeout = timeout  # custom attr; we pass timeout explicitly
    return session


def get_aphia_rank(session: requests.Session, base_url: str, aphia_id: int) -> Tuple[str, str, str, str, str, str]:
    """
    Fetch (rank, status, scientificname, valid_AphiaID, valid_name, valid_rank) for a single AphiaID
    using WoRMS REST API: /AphiaRecordByAphiaID/{aphia_id}

    Returns empty strings on any error (so caller can write blanks).
    """
    url = f"{base_url.rstrip('/')}/AphiaRecordByAphiaID/{aphia_id}"
    try:
        resp = session.get(url, headers={"Accept": "application/json"}, timeout=session.request_timeout)
    except requests.RequestException:
        return "", "", "", "", "", ""

    if resp.status_code != 200:
        return "", "", "", "", "", ""

    try:
        data = resp.json() or {}
    except ValueError:
        return "", "", "", "", "", ""

    rank            = str(data.get("rank") or "")
    status          = str(data.get("status") or "")
    scientificname  = str(data.get("scientificname") or "")
    valid_AphiaID   = ""
    if data.get("valid_AphiaID") is not None:
        # Coerce to string to keep CSV consistent even if null/int
        valid_AphiaID = str(data.get("valid_AphiaID"))
    valid_name      = str(data.get("valid_name") or "")

    # Get valid_rank
    valid_rank = ""
    if valid_AphiaID:
        if str(valid_AphiaID) == str(aphia_id):
            # If valid_AphiaID equals current aphia_id, use the same rank
            valid_rank = rank
        else:
            # If different, query the valid_AphiaID's rank
            try:
                valid_resp = session.get(f"{base_url.rstrip('/')}/AphiaRecordByAphiaID/{valid_AphiaID}", 
                                       headers={"Accept": "application/json"}, 
                                       timeout=session.request_timeout)
                if valid_resp.status_code == 200:
                    valid_data = valid_resp.json() or {}
                    valid_rank = str(valid_data.get("rank") or "")
            except (requests.RequestException, ValueError):
                pass
    
    return rank, status, scientificname, valid_AphiaID, valid_name, valid_rank


# ------------------------------ CSV utilities -------------------------------- #

def read_rows(csv_path: str) -> Tuple[List[Dict[str, str]], csv.Dialect]:
    """
    Read all rows from CSV/TSV with delimiter auto-detection.
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
        # Normalize: strip whitespace; coerce None -> ""
        row = {(k.strip() if k else k): (v.strip() if v is not None else "") for k, v in r.items()}
        rows.append(row)
    return rows, dialect


def write_rows(csv_path: str, rows: List[Dict[str, str]], fieldnames: List[str], dialect: csv.Dialect) -> None:
    """
    Write rows to CSV using detected delimiter but enforce safe quoting to avoid
    _csv.Error: need to escape, but no escapechar set
    """
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            dialect=dialect,                 # keep delimiter & line terminator
            quoting=csv.QUOTE_MINIMAL,       # ensure safe quoting
            quotechar=getattr(dialect, "quotechar", '"') or '"',
            escapechar=getattr(dialect, "escapechar", "\\") or "\\",
            doublequote=True,
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


# ------------------------------ Main workflow -------------------------------- #

def collect_unique_aphia_ids(rows: List[Dict[str, str]]) -> List[int]:
    """
    Collect unique, valid numeric AphiaIDs from 'source_id' column.
    """
    seen = set()
    out: List[int] = []
    for r in rows:
        sid = (r.get("source_id") or "").strip()
        if not sid:
            continue
        try:
            val = int(sid)
        except ValueError:
            continue
        if val not in seen:
            seen.add(val)
            out.append(val)
    return out


def enrich_rows_with_worms(rows: List[Dict[str, str]],
                           base_url: str,
                           workers: int = 5) -> None:
    """
    Mutates `rows` in-place by adding WoRMS fields populated via REST lookups
    using source_id (AphiaID).
    Rows with empty/invalid source_id get blanks.

    Adds/updates columns:
      rank, scientificname, status, valid_AphiaID, valid_name
    """
    target_cols = ("rank", "scientificname", "status", "valid_AphiaID", "valid_name", "valid_rank")
    for r in rows:
        for c in target_cols:
            if c not in r:
                r[c] = ""

    # Gather unique AphiaIDs
    aphia_ids = collect_unique_aphia_ids(rows)
    if not aphia_ids:
        return  # nothing to look up

    # Cache lookups: AphiaID -> (rank, status, scientificname, valid_AphiaID, valid_name, valid_rank)
    cache: Dict[int, Tuple[str, str, str, str, str, str]] = {}

    session = make_session()

    # Parallelize lookups (be gentle with the API)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        future_map = {
            ex.submit(get_aphia_rank, session, base_url, aid): aid
            for aid in aphia_ids
        }
        for fut in as_completed(future_map):
            aid = future_map[fut]
            try:
                cache[aid] = fut.result()
            except Exception:
                cache[aid] = ("", "", "", "", "", "")

    # Populate rows using cache; blank on missing/invalid source_id
    for r in rows:
        sid = (r.get("source_id") or "").strip()
        try:
            aid = int(sid) if sid else None
        except ValueError:
            aid = None

        if aid is not None and aid in cache:
            rank, status, scientificname, valid_AphiaID, valid_name, valid_rank = cache[aid]
            r["rank"] = rank
            r["status"] = status
            r["scientificname"] = scientificname
            r["valid_AphiaID"] = valid_AphiaID
            r["valid_name"] = valid_name
            r["valid_rank"] = valid_rank
        else:
            # Ensure blanks if no lookup
            r["rank"] = r.get("rank", "") or ""
            r["status"] = r.get("status", "") or ""
            r["scientificname"] = r.get("scientificname", "") or ""
            r["valid_AphiaID"] = r.get("valid_AphiaID", "") or ""
            r["valid_name"] = r.get("valid_name", "") or ""
            r["valid_rank"] = r.get("valid_rank", "") or ""


def fill_missing_ranks_recursive(rows: List[Dict[str, str]]) -> None:
    """Iteratively fill ranks for rows (no source_id, empty rank) using ancestor ranks.
    After that, assign 'Arbitrary' to any rows still missing a rank.

    The ladder is [Species, Genus, Family, Order, Class, Phylum]. In each pass,
    any row whose rank is empty can adopt the immediate lower rank of its nearest
    ancestor that currently has a recognized (non-empty) rank. Repeat until a full
    pass yields no changes.
    """
    # # Normalized hierarchy (lowercase) and canonical capitalization mapping
    # rank_hierarchy = ["species", "genus", "family", "class", "phylum"]
    # canonical = {r: r.capitalize() for r in rank_hierarchy}

    # # Build index for quick ancestor lookup by id (treat keys as strings)
    # id_to_row: Dict[str, Dict[str, str]] = {}
    # for r in rows:
    #     rid = r.get("id")
    #     if rid:
    #         id_to_row[str(rid)] = r

    # def nearest_ranked_ancestor(child: Dict[str, str]) -> Optional[str]:
    #     ancestor_id = (child.get("parent_id") or "").strip()
    #     visited = set()
    #     while ancestor_id:
    #         if ancestor_id in visited:
    #             break  # cycle guard
    #         visited.add(ancestor_id)

    #         anc = id_to_row.get(ancestor_id)
    #         if not anc:
    #             break
    #         anc_rank_raw = (anc.get("rank") or "").strip().lower()
    #         if anc_rank_raw in rank_hierarchy:
    #             return anc_rank_raw
    #         ancestor_id = (anc.get("parent_id") or "").strip()
    #     return None

    # # Iteratively fill ranks based on ancestors
    # changed = True
    # while changed:
    #     changed = False
    #     for r in rows:
    #         if (r.get("rank") or "").strip():
    #             continue
    #         if (r.get("source_id") or "").strip():
    #             continue

    #         anc_rank = nearest_ranked_ancestor(r)
    #         if not anc_rank:
    #             continue
    #         idx = rank_hierarchy.index(anc_rank)
    #         if idx > 0:
    #             r["rank"] = canonical[rank_hierarchy[idx - 1]]
    #             changed = True

    # After iterative filling, assign 'Arbitrary' to any rows still missing rank
    for r in rows:
        if not (r.get("source_id") or "").strip():
            r["rank"] = "Arbitrary"

            

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Populate WoRMS (Aphia) fields into CSV.")
    p.add_argument("input", help="Path to input CSV/TSV")
    p.add_argument("output", help="Path to output CSV")
    p.add_argument("--base-url", default="https://www.marinespecies.org/rest",
                   help="WoRMS REST base URL (default: %(default)s)")
    p.add_argument("--workers", type=int, default=5,
                   help="Concurrent requests (default: %(default)s). Use small values to be polite.")
    args = p.parse_args(argv)

    rows, dialect = read_rows(args.input)
    enrich_rows_with_worms(rows, base_url=args.base_url, workers=args.workers)

    # Perform recursive, multi-pass rank backfill for rows lacking source_id and rank
    fill_missing_ranks_recursive(rows)

    # Compose fieldnames: preserve original order and append new columns if needed
    existing_fields = list(rows[0].keys()) if rows else []
    for col in ("rank", "scientificname", "status", "valid_AphiaID", "valid_name"):
        if col not in existing_fields:
            existing_fields.append(col)

    write_rows(args.output, rows, existing_fields, dialect)
    return 0


if __name__ == "__main__":
    sys.exit(main())
