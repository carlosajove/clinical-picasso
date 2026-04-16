"""Corpus endpoints — dashboard stats and document listing."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Query

from api.deps import get_records

router = APIRouter()


@router.get("/stats")
def corpus_stats() -> dict:
    """Aggregate stats for the dashboard."""
    records = get_records()

    type_counter: Counter[str] = Counter()
    format_counter: Counter[str] = Counter()
    language_counter: Counter[str] = Counter()
    therapeutic_counter: Counter[str] = Counter()
    intervention_set: set[str] = set()
    trial_set: set[str] = set()
    phase_counter: Counter[str] = Counter()

    for r in records.values():
        primary = r.classes[0].class_name.value if r.classes else "Unknown"
        type_counter[primary] += 1

        ext = Path(r.filename).suffix.lower() or "unknown"
        format_counter[ext] += 1

        if r.country:
            language_counter[r.country] += 1

        if r.therapeutic_area:
            therapeutic_counter[r.therapeutic_area] += 1

        if r.intervention:
            intervention_set.add(r.intervention)

        if r.sponsor_protocol_id:
            trial_set.add(r.sponsor_protocol_id)

        if r.phase:
            phase_counter[r.phase] += 1

    return {
        "total_documents": len(records),
        "by_type": dict(type_counter.most_common()),
        "by_format": dict(format_counter.most_common()),
        "by_country": dict(language_counter.most_common()),
        "by_therapeutic_area": dict(therapeutic_counter.most_common()),
        "by_phase": dict(phase_counter.most_common()),
        "interventions": sorted(intervention_set),
        "trial_count": len(trial_set),
        "document_classes": len(type_counter),
        "file_formats": len(format_counter),
        "countries": len(language_counter),
        "therapeutic_areas": len(therapeutic_counter),
    }


@router.get("/documents")
def list_documents(
    doc_type: str | None = Query(None),
    trial: str | None = Query(None),
    country: str | None = Query(None),
    status: str | None = Query(None),
) -> list[dict]:
    """List all documents (excluding heavy content field)."""
    records = get_records()
    results = []
    for r in records.values():
        primary = r.classes[0].class_name.value if r.classes else "Unknown"

        if doc_type and primary != doc_type:
            continue
        if trial and r.sponsor_protocol_id != trial:
            continue
        if country and r.country != country:
            continue

        results.append({
            "doc_id": r.raw_sha256[:16],
            "filename": r.filename,
            "document_type": primary,
            "confidence": r.classes[0].confidence if r.classes else 0,
            "version": r.version,
            "country": r.country,
            "site_id": r.site_id,
            "sponsor_protocol_id": r.sponsor_protocol_id,
            "sponsor_name": r.sponsor_name,
            "trial_title": r.trial_title,
            "intervention": r.intervention,
            "indication": r.indication,
            "therapeutic_area": r.therapeutic_area,
            "phase": r.phase,
            "summary": r.summary,
            "references_to": r.references_to,
            "raw_sha256": r.raw_sha256,
        })

    return results


@router.get("/documents/{doc_id}")
def get_document(doc_id: str) -> dict:
    """Get a single document by doc_id (sha256 prefix)."""
    records = get_records()
    for sha, r in records.items():
        if sha.startswith(doc_id) or sha[:16] == doc_id:
            primary = r.classes[0].class_name.value if r.classes else "Unknown"
            return {
                "doc_id": r.raw_sha256[:16],
                "filename": r.filename,
                "document_type": primary,
                "classes": [
                    {"class_name": c.class_name.value, "confidence": c.confidence, "reasoning": c.reasoning}
                    for c in r.classes
                ],
                "confidence": r.classes[0].confidence if r.classes else 0,
                "version": r.version,
                "country": r.country,
                "site_id": r.site_id,
                "sponsor_protocol_id": r.sponsor_protocol_id,
                "sponsor_name": r.sponsor_name,
                "trial_title": r.trial_title,
                "intervention": r.intervention,
                "indication": r.indication,
                "therapeutic_area": r.therapeutic_area,
                "phase": r.phase,
                "summary": r.summary,
                "references_to": r.references_to,
                "raw_sha256": r.raw_sha256,
            }
    return {"error": "not found"}
