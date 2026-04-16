"""Generate an audit-ready cascade report as JSON."""

from __future__ import annotations

import json
from collections import defaultdict

from src.cascade.impact_analyzer import CascadeResult, AffectedDocument
from src.cascade.diff_engine import SemanticDiff


def generate_report(
    cascade: CascadeResult,
    diff: SemanticDiff | None = None,
) -> dict:
    """Build a structured report grouped by country, doc type, and urgency."""

    # Group by country
    by_country: dict[str, list[AffectedDocument]] = defaultdict(list)
    for doc in cascade.affected:
        by_country[doc.country or "Global"].append(doc)

    countries = []
    for country, docs in sorted(by_country.items()):
        # Group by doc type within country
        by_type: dict[str, list[dict]] = defaultdict(list)
        for doc in docs:
            by_type[doc.document_type].append({
                "doc_id": doc.doc_id,
                "source_file": doc.source_file,
                "site_id": doc.site_id,
                "edge_type": doc.edge_type,
                "urgency": doc.urgency,
            })

        countries.append({
            "country": country,
            "document_count": len(docs),
            "by_type": dict(by_type),
        })

    report = {
        "trigger_doc_id": cascade.trigger_doc_id,
        "total_affected": len(cascade.affected),
        "by_country": countries,
    }

    if diff is not None:
        report["diff"] = {
            "old_doc_id": diff.old_doc_id,
            "new_doc_id": diff.new_doc_id,
            "summary": diff.summary,
            "changes": [
                {
                    "section": c.section,
                    "change_type": c.change_type,
                    "description": c.description,
                }
                for c in diff.changes
            ],
        }

    return report


def report_to_json(report: dict, indent: int = 2) -> str:
    """Serialize the report to a JSON string."""
    return json.dumps(report, indent=indent, ensure_ascii=False)
