"""Traverse the graph to find all documents affected by a change.

Runs one query per edge type (DerivedFrom, References, Governs) and
unions the results.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.graph.client import OmniGraphClient

log = logging.getLogger(__name__)


@dataclass
class AffectedDocument:
    """One document impacted by the change."""
    doc_id: str
    document_type: str
    country: str | None
    site_id: str | None
    source_file: str | None
    edge_type: str        # which edge connected it to the trigger
    urgency: int          # 1=high, 2=medium, 3=low


@dataclass
class CascadeResult:
    """Full impact analysis from a trigger document."""
    trigger_doc_id: str
    affected: list[AffectedDocument] = field(default_factory=list)


# Document types ordered by urgency (regulatory > patient-facing > admin).
_URGENCY: dict[str, int] = {
    "ICF": 1,
    "CSP": 1,
    "SmPC / DSUR / DSMB Charter": 1,
    "IB": 2,
    "CSR": 2,
    "eTMF": 2,
    "Synopsis": 2,
    "CRF": 3,
    "Patient Questionnaire": 3,
    "Info Sheet": 3,
    "Medical Publications": 3,
    "NOISE": 3,
}


def analyze_impact(
    trigger_doc_id: str,
    client: OmniGraphClient,
) -> CascadeResult:
    """Find all current documents affected by *trigger_doc_id*."""
    result = CascadeResult(trigger_doc_id=trigger_doc_id)
    seen: set[str] = set()

    for query_name, edge_type in [
        ("cascade_derived", "DerivedFrom"),
        ("cascade_references", "References"),
        ("cascade_governed", "Governs"),
    ]:
        rows = client.query(query_name, {"changed_id": trigger_doc_id})
        for row in rows:
            did = row["affected.doc_id"]
            if did in seen or did == trigger_doc_id:
                continue
            seen.add(did)

            doc_type = row.get("affected.document_type", "unknown")
            result.affected.append(AffectedDocument(
                doc_id=did,
                document_type=doc_type,
                country=row.get("affected.country"),
                site_id=row.get("affected.site_id"),
                source_file=row.get("affected.source_file"),
                edge_type=edge_type,
                urgency=_URGENCY.get(doc_type, 3),
            ))

    result.affected.sort(key=lambda a: (a.urgency, a.document_type, a.country or ""))
    log.info(
        "Cascade from %s: %d documents affected",
        trigger_doc_id, len(result.affected),
    )
    return result
