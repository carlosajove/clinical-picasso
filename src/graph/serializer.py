"""Convert ExtractionRecord → OmniGraph JSONL lines.

JSONL format:
  Nodes:  {"type": "NodeType", "data": {field: value, ...}}
  Edges:  {"edge": "EdgeType", "from": "src_key", "to": "dst_key", "data": {...}}
"""

from __future__ import annotations

import json

from src.extraction.schema import ExtractionRecord


def _pick_trial_key(record: ExtractionRecord) -> str | None:
    """Return the best available trial identifier to use as the Trial @key.

    Priority: sponsor_protocol_id > nct_id > eudract_id > eu_ct_id.
    Returns None if no trial ID is available.
    """
    return (
        record.sponsor_protocol_id
        or record.nct_id
        or record.eudract_id
        or record.eu_ct_id
    )


def serialize_document(record: ExtractionRecord) -> dict:
    """Build the Document node JSONL line."""
    primary = record.classes[0]
    return {
        "type": "Document",
        "data": {
            "doc_id": record.raw_sha256[:16],
            "source_file": record.filename,
            "content_hash": record.raw_sha256,
            "document_type": primary.class_name.value,
            "classification_confidence": primary.confidence,
            "raw_classes": json.dumps(
                [c.model_dump(mode="json") for c in record.classes]
            ),
            "version": record.version,
            "status": "active",
            "country": record.country,
            "site_id": record.site_id,
            "summary": record.summary,
            "sponsor_name": record.sponsor_name,
            "sponsor_protocol_id": record.sponsor_protocol_id,
            "trial_title": record.trial_title,
            "intervention": record.intervention,
            "indication": record.indication,
            "phase": record.phase,
        },
    }


def serialize_trial(record: ExtractionRecord) -> dict | None:
    """Build the Trial node JSONL line, or None if no trial ID exists."""
    key = _pick_trial_key(record)
    if key is None:
        return None
    return {
        "type": "Trial",
        "data": {
            "protocol_id": key,
            "nct_id": record.nct_id,
            "eudract_id": record.eudract_id,
            "title": record.trial_title,
            "phase": record.phase,
            "intervention": record.intervention,
            "indication": record.indication,
        },
    }


def serialize_belongs_to_trial(record: ExtractionRecord) -> dict | None:
    """Build the BelongsToTrial edge, or None if no trial ID exists."""
    trial_key = _pick_trial_key(record)
    if trial_key is None:
        return None
    return {
        "edge": "BelongsToTrial",
        "from": record.raw_sha256[:16],
        "to": trial_key,
    }


def serialize(record: ExtractionRecord) -> list[dict]:
    """Convert one ExtractionRecord into JSONL lines for ``omnigraph load``.

    Returns 1–3 lines: Document node, optionally Trial node + BelongsToTrial edge.
    """
    lines: list[dict] = []

    lines.append(serialize_document(record))

    trial = serialize_trial(record)
    if trial is not None:
        lines.append(trial)

    edge = serialize_belongs_to_trial(record)
    if edge is not None:
        lines.append(edge)

    return lines
