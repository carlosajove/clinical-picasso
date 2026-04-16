"""Shared dependencies for the API layer.

Singletons for OmniGraphClient and the extraction record cache.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.extraction.schema import ExtractionRecord
from src.graph.client import OmniGraphClient

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent
RECORDS_DIR = _ROOT / "out" / "records"
SCHEMA_PATH = _ROOT / "schema" / "clinical.pg"
QUERIES_DIR = _ROOT / "queries"
GRAPH_REPO = _ROOT / "graph_repo"
DATA_DIR = _ROOT / "data"

# Singletons — initialised at startup
_client: OmniGraphClient | None = None
_records: dict[str, ExtractionRecord] = {}


def get_client() -> OmniGraphClient:
    if _client is None:
        raise RuntimeError("OmniGraphClient not initialised — call init_client() first")
    return _client


def init_client() -> OmniGraphClient:
    global _client
    _client = OmniGraphClient(
        repo_path=GRAPH_REPO,
        schema_path=SCHEMA_PATH,
        queries_dir=QUERIES_DIR,
    )
    return _client


def build_graph() -> None:
    """Initialise the graph repo and load all cached records into it.

    Idempotent — re-creates the graph from scratch each time to stay
    in sync with the extraction cache.
    """
    import shutil
    from src.graph.serializer import serialize
    from src.ingest.ingestion import ingest

    client = get_client()

    # Wipe and re-init so we always start clean
    if GRAPH_REPO.exists():
        shutil.rmtree(GRAPH_REPO)
    client.init()
    log.info("Graph repo initialised at %s", GRAPH_REPO)

    # Phase 1: load all document/trial nodes + BelongsToTrial edges
    records = get_records()
    all_lines: list[dict] = []

    from src.graph.serializer import (
        serialize_document,
        serialize_belongs_to_trial,
        _pick_trial_key,
    )

    # Aggregate trial metadata across all records so the Trial node
    # gets the richest data available (not just from the first record).
    trial_meta: dict[str, dict] = {}  # trial_key → merged fields
    for record in records.values():
        trial_key = _pick_trial_key(record)
        if not trial_key:
            continue
        if trial_key not in trial_meta:
            trial_meta[trial_key] = {
                "nct_id": None, "eudract_id": None,
                "title": None, "phase": None,
                "intervention": None, "indication": None,
            }
        meta = trial_meta[trial_key]
        meta["nct_id"] = meta["nct_id"] or record.nct_id
        meta["eudract_id"] = meta["eudract_id"] or record.eudract_id
        # Prefer English titles; among those, prefer longer (more descriptive)
        if record.trial_title:
            cur = meta["title"]
            new = record.trial_title
            new_is_ascii = all(ord(c) < 128 for c in new)
            cur_is_ascii = cur and all(ord(c) < 128 for c in cur)
            if not cur or (new_is_ascii and not cur_is_ascii) or (
                new_is_ascii == cur_is_ascii and len(new) > len(cur)
            ):
                meta["title"] = new
        meta["phase"] = meta["phase"] or record.phase
        meta["intervention"] = meta["intervention"] or record.intervention
        meta["indication"] = meta["indication"] or record.indication

    # Create Trial nodes from aggregated metadata
    for trial_key, meta in trial_meta.items():
        all_lines.append({
            "type": "Trial",
            "data": {
                "trial_key": trial_key,
                **meta,
            },
        })

    # Create Document nodes + BelongsToTrial edges
    for record in records.values():
        all_lines.append(serialize_document(record))
        edge_line = serialize_belongs_to_trial(record)
        if edge_line:
            all_lines.append(edge_line)

    if all_lines:
        client.load_jsonl(all_lines)
        log.info("Loaded %d JSONL lines (%d docs, %d trials)",
                 len(all_lines), len(records), len(trial_meta))

    # Phase 2: version resolution + edge discovery per document
    from src.ingest.version_resolver import resolve_version
    from src.ingest.linker import discover_edges

    edges_created = 0
    for record in records.values():
        # Version resolution
        version_match = resolve_version(record, client)
        if version_match is not None:
            try:
                client.mutate("add_supersedes", {
                    "new_id": record.raw_sha256[:16],
                    "old_id": version_match.superseded_doc_id,
                    "reason": version_match.reason,
                })
                client.mutate("mark_superseded", {"doc_id": version_match.superseded_doc_id})
                edges_created += 1
            except Exception as e:
                log.warning("Supersedes edge failed: %s", e)

        # Edge discovery
        edges = discover_edges(record, client)
        for edge in edges:
            try:
                client.mutate(edge.edge_type, edge.params)
                edges_created += 1
            except Exception as e:
                log.warning("Edge %s failed: %s", edge.edge_type, e)

    log.info("Graph build complete: %d relationship edges created", edges_created)


def load_records() -> dict[str, ExtractionRecord]:
    """Load all cached ExtractionRecords from disk into memory."""
    global _records
    _records = {}
    if not RECORDS_DIR.exists():
        log.warning("Records dir %s does not exist", RECORDS_DIR)
        return _records
    for path in RECORDS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            record = ExtractionRecord(**data)
            _records[record.raw_sha256] = record
        except Exception as e:
            log.warning("Failed to load %s: %s", path.name, e)
    log.info("Loaded %d extraction records", len(_records))
    return _records


def get_records() -> dict[str, ExtractionRecord]:
    return _records


def refresh_records() -> dict[str, ExtractionRecord]:
    """Reload records from disk (call after ingestion)."""
    return load_records()
