"""Core iterative ingestion — add one document at a time to the graph.

Each call to ``ingest()`` uses the current graph state as context for
version resolution and edge discovery. Returns a report of every change
made to the graph.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.extraction.schema import ExtractionRecord
from src.graph.client import OmniGraphClient
from src.graph.serializer import serialize, _pick_trial_key
from src.ingest.version_resolver import resolve_version, VersionMatch
from src.ingest.linker import discover_edges, DiscoveredEdge

log = logging.getLogger(__name__)


@dataclass
class GraphChange:
    """One mutation made to the graph during ingestion."""
    action: str         # "created_node", "created_edge", "updated_status"
    target_type: str    # "Document", "Trial", "BelongsToTrial", "Supersedes", etc.
    details: dict       # key/value pairs describing the change


@dataclass
class IngestResult:
    """Full report of what changed in the graph when a document was ingested."""
    doc_id: str
    document_type: str
    trial_key: str | None
    is_orphan: bool
    changes: list[GraphChange] = field(default_factory=list)


def ingest(
    record: ExtractionRecord,
    client: OmniGraphClient,
) -> IngestResult:
    """Ingest a single ExtractionRecord into the graph.

    Returns a report of every change made.
    """
    doc_id = record.raw_sha256[:16]
    trial_key = _pick_trial_key(record)
    primary_type = record.classes[0].class_name.value
    changes: list[GraphChange] = []

    # 1. Load Document node (and Trial + BelongsToTrial if applicable)
    lines = serialize(record)
    client.load_jsonl(lines)

    changes.append(GraphChange(
        action="created_node",
        target_type="Document",
        details={"doc_id": doc_id, "document_type": primary_type, "source_file": record.filename},
    ))
    if trial_key is not None:
        changes.append(GraphChange(
            action="created_node",
            target_type="Trial",
            details={"protocol_id": trial_key},
        ))
        changes.append(GraphChange(
            action="created_edge",
            target_type="BelongsToTrial",
            details={"from": doc_id, "to": trial_key},
        ))

    log.info("Loaded %s (%s) — %d JSONL lines", doc_id, primary_type, len(lines))

    # 2. Version resolution
    version_match = resolve_version(record, client)
    if version_match is not None:
        client.mutate("add_supersedes", {
            "new_id": doc_id,
            "old_id": version_match.superseded_doc_id,
            "reason": version_match.reason,
        })
        client.mutate("mark_superseded", {"doc_id": version_match.superseded_doc_id})

        changes.append(GraphChange(
            action="created_edge",
            target_type="Supersedes",
            details={
                "from": doc_id,
                "to": version_match.superseded_doc_id,
                "reason": version_match.reason,
            },
        ))
        changes.append(GraphChange(
            action="updated_status",
            target_type="Document",
            details={
                "doc_id": version_match.superseded_doc_id,
                "status": "superseded",
            },
        ))

        log.info("  Supersedes %s (%s)", version_match.superseded_doc_id, version_match.reason)

    # 3. Edge discovery
    edges = discover_edges(record, client)
    for edge in edges:
        try:
            client.mutate(edge.edge_type, edge.params)
            changes.append(GraphChange(
                action="created_edge",
                target_type=edge.edge_type.replace("add_", ""),
                details=edge.params,
            ))
            log.info("  Edge: %s %s", edge.edge_type, edge.params)
        except RuntimeError as e:
            log.warning("  Edge failed: %s — %s", edge.edge_type, e)

    is_orphan = trial_key is None and len([
        c for c in changes
        if c.action == "created_edge" and c.target_type not in ("BelongsToTrial",)
    ]) == 0

    return IngestResult(
        doc_id=doc_id,
        document_type=primary_type,
        trial_key=trial_key,
        is_orphan=is_orphan,
        changes=changes,
    )
