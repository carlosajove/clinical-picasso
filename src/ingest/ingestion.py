"""Core iterative ingestion — add one document at a time to the graph.

Each call to ``ingest()`` uses the current graph state as context for
classification refinement, version resolution, and edge discovery.
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
class IngestResult:
    """Summary of what happened during ingestion of one document."""
    doc_id: str
    document_type: str
    trial_key: str | None
    is_orphan: bool
    version_match: VersionMatch | None = None
    edges_created: list[str] = field(default_factory=list)


def ingest(
    record: ExtractionRecord,
    client: OmniGraphClient,
) -> IngestResult:
    """Ingest a single ExtractionRecord into the graph.

    Steps:
      1. Serialize and load Document + Trial nodes + BelongsToTrial edge
      2. Version resolution — detect if this supersedes an existing doc
      3. Edge discovery — deterministic rules for DerivedFrom, References, Governs
      4. All mutations committed as OmniGraph snapshots
    """
    doc_id = record.raw_sha256[:16]
    trial_key = _pick_trial_key(record)
    primary_type = record.classes[0].class_name.value

    # 1. Load the document (and trial/edge if applicable)
    lines = serialize(record)
    client.load_jsonl(lines)
    log.info("Loaded %s (%s) — %d JSONL lines", doc_id, primary_type, len(lines))

    # 2. Version resolution
    version_match = resolve_version(record, client)
    if version_match is not None:
        client.mutate(
            "add_supersedes",
            {
                "new_id": doc_id,
                "old_id": version_match.superseded_doc_id,
                "reason": version_match.reason,
            },
        )
        client.mutate(
            "mark_superseded",
            {"doc_id": version_match.superseded_doc_id},
        )
        log.info(
            "  Version: %s supersedes %s (%s)",
            doc_id, version_match.superseded_doc_id, version_match.reason,
        )

    # 3. Edge discovery
    edges = discover_edges(record, client)
    edges_created = []
    for edge in edges:
        try:
            client.mutate(edge.edge_type, edge.params)
            edges_created.append(edge.edge_type)
            log.info("  Edge: %s %s", edge.edge_type, edge.params)
        except RuntimeError as e:
            log.warning("  Edge failed: %s %s — %s", edge.edge_type, edge.params, e)

    return IngestResult(
        doc_id=doc_id,
        document_type=primary_type,
        trial_key=trial_key,
        is_orphan=trial_key is None and not edges_created,
        version_match=version_match,
        edges_created=edges_created,
    )
