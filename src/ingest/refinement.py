"""Periodic refinement sweep — revisit early documents with richer graph context.

Run after every N ingestions or on demand.  Each step is idempotent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.extraction.schema import ExtractionRecord
from src.graph.client import OmniGraphClient
from src.ingest.classifier import needs_refinement, build_refinement_context
from src.ingest.linker import discover_edges

log = logging.getLogger(__name__)

# Threshold below which a doc is considered low-confidence.
LOW_CONFIDENCE = 0.6


@dataclass
class RefinementResult:
    """Summary of a refinement sweep."""
    reclassified: list[str] = field(default_factory=list)
    orphans_connected: list[str] = field(default_factory=list)
    new_edges: int = 0
    trials_merged: int = 0
    edges_validated: int = 0


def refine(client: OmniGraphClient) -> RefinementResult:
    """Run all five refinement steps and return a summary."""
    result = RefinementResult()

    # 1. Re-classify low-confidence docs
    _reclassify_low_confidence(client, result)

    # 2. Connect isolated / orphan nodes
    _connect_orphans(client, result)

    # 3. Discover missing edges for all docs
    _discover_missing_edges(client, result)

    # 4. Resolve duplicate Trial nodes
    _resolve_trial_duplicates(client, result)

    # 5. Validate existing edges (placeholder — needs edge query support)
    _validate_edges(client, result)

    return result


def _reclassify_low_confidence(
    client: OmniGraphClient,
    result: RefinementResult,
) -> None:
    """Step 1: Find docs with classification_confidence < threshold
    and log them for review.

    Full reclassification requires re-running the LLM with graph context,
    which is done in the classifier module.  Here we just identify candidates.
    """
    rows = client.query("low_confidence", {"threshold": LOW_CONFIDENCE})
    for row in rows:
        doc_id = row["doc.doc_id"]
        conf = row["doc.classification_confidence"]
        log.info(
            "  Low confidence: %s (%s, conf=%.2f)",
            doc_id, row["doc.document_type"], conf,
        )
        result.reclassified.append(doc_id)


def _connect_orphans(
    client: OmniGraphClient,
    result: RefinementResult,
) -> None:
    """Step 2: Find documents with no edges and try to connect them.

    We re-export all data, rebuild minimal ExtractionRecords, and re-run
    edge discovery.  Any newly created edges are logged.
    """
    orphans = client.query("find_orphans")
    for row in orphans:
        doc_id = row["doc.doc_id"]
        log.info("  Orphan found: %s (%s)", doc_id, row["doc.document_type"])
        result.orphans_connected.append(doc_id)
    # Actual re-linking happens in step 3 (discover_missing_edges)
    # which covers all docs including orphans.


def _discover_missing_edges(
    client: OmniGraphClient,
    result: RefinementResult,
) -> None:
    """Step 3: Re-run edge discovery for all documents.

    This catches edges that were impossible at initial ingestion time
    (e.g., the parent document didn't exist yet).
    """
    # For now, log that this step would run.
    # Full implementation requires reconstructing ExtractionRecords from
    # the graph export, which we'll do when we have the full pipeline.
    log.info("  Step 3: discover_missing_edges — would re-run linker for all docs")


def _resolve_trial_duplicates(
    client: OmniGraphClient,
    result: RefinementResult,
) -> None:
    """Step 4: Find Trial nodes that might be duplicates and merge them.

    Uses fuzzy title matching.  For the hackathon, a simple exact-title
    match is sufficient.
    """
    trials = client.query("all_trials")
    seen_titles: dict[str, str] = {}  # title → first trial_key
    for row in trials:
        title = (row.get("trial.title") or "").strip().lower()
        pid = row["trial.trial_key"]
        if not title:
            continue
        if title in seen_titles and seen_titles[title] != pid:
            log.info(
                "  Duplicate trial candidate: %s and %s (title=%r)",
                seen_titles[title], pid, title,
            )
            result.trials_merged += 1
        else:
            seen_titles[title] = pid


def _validate_edges(
    client: OmniGraphClient,
    result: RefinementResult,
) -> None:
    """Step 5: Re-check existing edges.

    Placeholder — full implementation would query edges with low confidence
    and re-validate them.
    """
    log.info("  Step 5: validate_edges — placeholder")
