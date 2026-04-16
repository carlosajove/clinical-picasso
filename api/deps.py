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
    seen_trials: set[str] = set()

    for record in records.values():
        from src.graph.serializer import (
            serialize_document,
            serialize_trial,
            serialize_belongs_to_trial,
            _pick_trial_key,
        )
        all_lines.append(serialize_document(record))

        trial_key = _pick_trial_key(record)
        if trial_key and trial_key not in seen_trials:
            trial_line = serialize_trial(record)
            if trial_line:
                all_lines.append(trial_line)
                seen_trials.add(trial_key)

        edge_line = serialize_belongs_to_trial(record)
        if edge_line:
            all_lines.append(edge_line)

    if all_lines:
        client.load_jsonl(all_lines)
        log.info("Loaded %d JSONL lines (%d docs, %d trials)",
                 len(all_lines), len(records), len(seen_trials))

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
