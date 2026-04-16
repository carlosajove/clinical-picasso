"""Refine document classification using graph context."""

from __future__ import annotations

from src.extraction.schema import ExtractionRecord
from src.graph.client import OmniGraphClient
from src.graph.serializer import _pick_trial_key

# If the gap between the top two candidates is less than this,
# classification is considered ambiguous.
AMBIGUITY_THRESHOLD = 0.15


def needs_refinement(record: ExtractionRecord) -> bool:
    """Return True if classification is ambiguous and could benefit from
    graph context."""
    if len(record.classes) < 2:
        return False
    top = record.classes[0].confidence
    second = record.classes[1].confidence
    return (top - second) < AMBIGUITY_THRESHOLD


def get_trial_type_distribution(
    client: OmniGraphClient,
    trial_key: str,
) -> dict[str, int]:
    """Query the graph for how many documents of each type exist in a trial."""
    rows = client.query(
        "trial_documents",
        {"protocol_id": trial_key},
    )
    counts: dict[str, int] = {}
    for row in rows:
        doc_type = row.get("doc.document_type", "unknown")
        counts[doc_type] = counts.get(doc_type, 0) + 1
    return counts


def build_refinement_context(
    record: ExtractionRecord,
    client: OmniGraphClient,
) -> str | None:
    """Build a context string from the graph to help the LLM disambiguate.

    Returns None if there's not enough graph context to help.
    """
    trial_key = _pick_trial_key(record)
    if trial_key is None:
        return None

    distribution = get_trial_type_distribution(client, trial_key)
    if not distribution:
        return None

    lines = ["Document type distribution for this trial:"]
    for doc_type, count in sorted(distribution.items()):
        lines.append(f"  - {doc_type}: {count}")

    return "\n".join(lines)
