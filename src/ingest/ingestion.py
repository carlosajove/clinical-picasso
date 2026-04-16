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
from src.graph.serializer import (
    serialize_document,
    serialize_trial,
    serialize_belongs_to_trial,
    serialize_phase,
    serialize_has_phase,
    serialize_belongs_to_phase,
    serialize_amends,
    _pick_trial_key,
    _make_phase_id,
)
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
    review_verdict: object | None = None          # ReviewVerdict when reviewer is used
    amendment_impact: list[dict] | None = None     # affected docs from amendment cascade


async def ingest(
    record: ExtractionRecord,
    client: OmniGraphClient,
    reviewer=None,
) -> IngestResult:
    """Ingest a single ExtractionRecord into the graph.

    Parameters
    ----------
    reviewer : DocumentReviewer | None
        If provided, runs the LLM reviewer agent after deterministic steps.

    Returns a report of every change made.
    """
    doc_id = record.raw_sha256[:16]
    trial_key = _pick_trial_key(record)
    primary_type = record.classes[0].class_name.value
    changes: list[GraphChange] = []

    # 1. Load Document node
    lines = [serialize_document(record)]
    changes.append(GraphChange(
        action="created_node",
        target_type="Document",
        details={"doc_id": doc_id, "document_type": primary_type, "source_file": record.filename},
    ))

    # Only create Trial node if it doesn't already exist
    if trial_key is not None:
        existing = client.query("find_trial", {"protocol_id": trial_key})
        if not existing:
            trial_line = serialize_trial(record)
            if trial_line is not None:
                lines.append(trial_line)
            changes.append(GraphChange(
                action="created_node",
                target_type="Trial",
                details={"protocol_id": trial_key},
            ))

        edge_line = serialize_belongs_to_trial(record)
        if edge_line is not None:
            lines.append(edge_line)
        changes.append(GraphChange(
            action="created_edge",
            target_type="BelongsToTrial",
            details={"from": doc_id, "to": trial_key},
        ))

    # Phase node creation
    if trial_key is not None and record.phase:
        phase_id = _make_phase_id(trial_key, record.phase)
        existing_phase = client.query("find_phase", {"phase_id": phase_id})
        if not existing_phase:
            phase_line = serialize_phase(record)
            if phase_line is not None:
                lines.append(phase_line)
            has_phase_line = serialize_has_phase(record)
            if has_phase_line is not None:
                lines.append(has_phase_line)
            changes.append(GraphChange(
                action="created_node",
                target_type="Phase",
                details={"phase_id": phase_id, "phase_label": record.phase},
            ))

        belongs_to_phase_line = serialize_belongs_to_phase(record)
        if belongs_to_phase_line is not None:
            lines.append(belongs_to_phase_line)
        changes.append(GraphChange(
            action="created_edge",
            target_type="BelongsToPhase",
            details={"from": doc_id, "to": phase_id},
        ))

    client.load_jsonl(lines)

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

    # 4. Reviewer agent (optional, LLM-powered)
    review_verdict = None
    amendment_impact = None
    if reviewer is not None:
        review_verdict, amendment_impact = await _run_reviewer(
            reviewer, record, doc_id, trial_key, client, changes,
        )

    is_orphan = trial_key is None and len([
        c for c in changes
        if c.action == "created_edge" and c.target_type not in ("BelongsToTrial", "BelongsToPhase")
    ]) == 0

    return IngestResult(
        doc_id=doc_id,
        document_type=primary_type,
        trial_key=trial_key,
        is_orphan=is_orphan,
        changes=changes,
        review_verdict=review_verdict,
        amendment_impact=amendment_impact,
    )


async def _run_reviewer(reviewer, record, doc_id, trial_key, client, changes):
    """Run the reviewer agent and apply its suggestions to the graph."""
    try:
        verdict = await reviewer.review(record, client)
    except Exception as e:
        log.warning("  Reviewer failed for %s: %s", doc_id, e)
        return None, None

    # 4a. Reclassification
    if not verdict.classification_ok and verdict.reclassification is not None:
        reclass = verdict.reclassification
        try:
            client.mutate("update_document_type", {
                "doc_id": doc_id,
                "document_type": reclass.suggested_class,
                "classification_confidence": reclass.confidence,
            })
            changes.append(GraphChange(
                action="updated_status",
                target_type="Document",
                details={
                    "doc_id": doc_id,
                    "old_type": reclass.original_class,
                    "new_type": reclass.suggested_class,
                    "reason": reclass.reasoning,
                },
            ))
            log.info(
                "  Reclassified %s: %s -> %s (%s)",
                doc_id, reclass.original_class, reclass.suggested_class, reclass.reasoning,
            )
        except RuntimeError as e:
            log.warning("  Reclassification failed for %s: %s", doc_id, e)

    # 4b. Amendment detection + cascade
    amendment_impact = None
    if verdict.amendment.is_amendment:
        amendment_impact = _handle_amendment(
            verdict, doc_id, trial_key, client, changes,
        )

    # 4c. Suggested edges
    for suggestion in verdict.suggested_edges:
        try:
            edge_type = suggestion.edge_type
            edge_type_lower = edge_type.lower().replace("_", "")
            # Normalize params: the LLM may use different key names than our mutations expect
            params = dict(suggestion.params)
            params["from_doc_id"] = suggestion.from_doc_id
            params["to_doc_id"] = suggestion.to_doc_id
            # Map to mutation-expected parameter names per edge type
            if edge_type_lower == "references":
                mutation_params = {
                    "from_id": suggestion.from_doc_id,
                    "to_id": suggestion.to_doc_id,
                    "citation_text": params.get("citation_text", suggestion.reasoning),
                }
            elif edge_type_lower == "derivedfrom":
                mutation_params = {
                    "child_id": suggestion.from_doc_id,
                    "parent_id": suggestion.to_doc_id,
                    "derivation_type": params.get("derivation_type", "reviewer_suggested"),
                }
            elif edge_type_lower == "governs":
                mutation_params = {
                    "gov_id": suggestion.from_doc_id,
                    "doc_id": suggestion.to_doc_id,
                    "authority_type": params.get("authority_type", "reviewer_suggested"),
                }
            elif edge_type_lower == "amends":
                mutation_params = {
                    "amendment_id": suggestion.from_doc_id,
                    "base_id": suggestion.to_doc_id,
                    "amendment_label": params.get("amendment_label", ""),
                    "scope": params.get("scope", "global"),
                }
            else:
                log.warning("  Unknown edge type from reviewer: %s", edge_type)
                continue
            # Map edge type to mutation name
            mutation_name_map = {
                "references": "add_references",
                "derivedfrom": "add_derived_from",
                "governs": "add_governs",
                "amends": "add_amends",
            }
            mutation_name = mutation_name_map.get(edge_type_lower)
            if not mutation_name:
                log.warning("  No mutation for edge type: %s", edge_type)
                continue
            client.mutate(mutation_name, mutation_params)
            changes.append(GraphChange(
                action="created_edge",
                target_type=edge_type,
                details={**mutation_params, "reason": suggestion.reasoning},
            ))
            log.info("  Reviewer edge: %s %s", edge_type, mutation_params)
        except (RuntimeError, ValueError, KeyError) as e:
            log.warning("  Reviewer edge failed: %s — %s", suggestion.edge_type, e)

    if verdict.inconsistencies:
        for issue in verdict.inconsistencies:
            log.warning("  Inconsistency: %s", issue)

    return verdict, amendment_impact


def _handle_amendment(verdict, doc_id, trial_key, client, changes):
    """Create Amends edge and compute cascade impact."""
    amendment = verdict.amendment
    base_doc_id = amendment.base_doc_id

    # Fallback: find current base CSP in the same trial
    if base_doc_id is None and trial_key is not None:
        rows = client.query("find_amendment_targets", {
            "doc_type": "CSP",
            "trial_id": trial_key,
        })
        if rows:
            base_doc_id = rows[0]["doc.doc_id"]

    if base_doc_id is None:
        log.warning("  Amendment detected for %s but no base document found", doc_id)
        return None

    # Create Amends edge
    try:
        client.mutate("add_amends", {
            "amendment_id": doc_id,
            "base_id": base_doc_id,
            "amendment_label": amendment.amendment_label or "",
            "scope": amendment.scope or "global",
        })
        changes.append(GraphChange(
            action="created_edge",
            target_type="Amends",
            details={
                "from": doc_id,
                "to": base_doc_id,
                "amendment_label": amendment.amendment_label,
                "scope": amendment.scope,
            },
        ))
        log.info(
            "  Amendment: %s amends %s (label=%s, scope=%s)",
            doc_id, base_doc_id, amendment.amendment_label, amendment.scope,
        )
    except RuntimeError as e:
        log.warning("  Amends edge failed: %s", e)
        return None

    # Run cascade to find affected documents
    impact = []
    for cascade_query in ("cascade_derived", "cascade_references"):
        try:
            rows = client.query(cascade_query, {"changed_id": base_doc_id})
            for row in rows:
                impact.append({
                    "doc_id": row["$affected.doc_id"] if "$affected.doc_id" in row else row.get("affected.doc_id", row.get("doc_id")),
                    "document_type": row.get("$affected.document_type", row.get("affected.document_type", "")),
                    "source_file": row.get("$affected.source_file", row.get("affected.source_file", "")),
                    "cascade_type": cascade_query,
                })
        except RuntimeError as e:
            log.warning("  Cascade query %s failed: %s", cascade_query, e)

    if impact:
        log.info("  Amendment cascade: %d documents affected", len(impact))
    return impact if impact else None
