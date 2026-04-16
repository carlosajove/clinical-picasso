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
            "version_ordinal": record.version_ordinal,
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
            "trial_key": key,
            "nct_id": record.nct_id,
            "eudract_id": record.eudract_id,
            "eu_ct_id": record.eu_ct_id,
            "isrctn_id": record.isrctn_id,
            "utn_id": record.utn_id,
            "ind_number": record.ind_number,
            "cta_number": record.cta_number,
            "sponsor_name": record.sponsor_name,
            "acronym": record.trial_acronym,
            "therapeutic_area": record.therapeutic_area,
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


def _make_phase_id(trial_key: str, phase_label: str) -> str:
    """Build the deterministic composite key for a Phase node."""
    return f"{trial_key}::phase:{phase_label}"


def serialize_phase(record: ExtractionRecord) -> dict | None:
    """Build the Phase node JSONL line, or None if no trial/phase."""
    trial_key = _pick_trial_key(record)
    if trial_key is None or not record.phase:
        return None
    phase_id = _make_phase_id(trial_key, record.phase)
    return {
        "type": "Phase",
        "data": {
            "phase_id": phase_id,
            "trial_id": trial_key,
            "phase_label": record.phase,
        },
    }


def serialize_has_phase(record: ExtractionRecord) -> dict | None:
    """Build the HasPhase edge (Trial → Phase), or None if no trial/phase."""
    trial_key = _pick_trial_key(record)
    if trial_key is None or not record.phase:
        return None
    phase_id = _make_phase_id(trial_key, record.phase)
    return {
        "edge": "HasPhase",
        "from": trial_key,
        "to": phase_id,
    }


def serialize_belongs_to_phase(record: ExtractionRecord) -> dict | None:
    """Build the BelongsToPhase edge (Document → Phase), or None if no trial/phase."""
    trial_key = _pick_trial_key(record)
    if trial_key is None or not record.phase:
        return None
    phase_id = _make_phase_id(trial_key, record.phase)
    return {
        "edge": "BelongsToPhase",
        "from": record.raw_sha256[:16],
        "to": phase_id,
    }


def serialize_amends(
    amendment_doc_id: str,
    base_doc_id: str,
    amendment_label: str | None = None,
    scope: str | None = None,
) -> dict:
    """Build the Amends edge JSONL line."""
    return {
        "edge": "Amends",
        "from": amendment_doc_id,
        "to": base_doc_id,
        "data": {
            "amendment_label": amendment_label,
            "scope": scope,
        },
    }


def serialize(record: ExtractionRecord) -> list[dict]:
    """Convert one ExtractionRecord into JSONL lines for ``omnigraph load``.

    Returns 1–6 lines: Document node, optionally Trial node + BelongsToTrial edge,
    optionally Phase node + HasPhase edge + BelongsToPhase edge.
    """
    lines: list[dict] = []

    lines.append(serialize_document(record))

    trial = serialize_trial(record)
    if trial is not None:
        lines.append(trial)

    edge = serialize_belongs_to_trial(record)
    if edge is not None:
        lines.append(edge)

    phase = serialize_phase(record)
    if phase is not None:
        lines.append(phase)

    has_phase = serialize_has_phase(record)
    if has_phase is not None:
        lines.append(has_phase)

    belongs_to_phase = serialize_belongs_to_phase(record)
    if belongs_to_phase is not None:
        lines.append(belongs_to_phase)

    return lines
