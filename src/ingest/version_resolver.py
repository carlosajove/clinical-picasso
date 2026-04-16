"""Detect whether a new document supersedes an existing one in the graph,
or vice versa (bidirectional — handles out-of-order ingestion).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.extraction.schema import ExtractionRecord
from src.graph.client import OmniGraphClient
from src.graph.serializer import _pick_trial_key


@dataclass
class VersionMatch:
    """Result of version resolution."""
    superseded_doc_id: str
    superseder_doc_id: str
    reason: str
    direction: str   # "forward" = new supersedes existing, "reverse" = existing supersedes new


def resolve_version(
    record: ExtractionRecord,
    client: OmniGraphClient,
) -> list[VersionMatch]:
    """Check version relationships between *record* and existing docs in the graph.

    Returns a list of VersionMatch objects. May contain multiple entries
    when the new doc supersedes several older versions (e.g. v3.0 arriving
    when v1.0 and v2.0 are both active).

    Also detects the reverse: if an older doc is ingested after a newer one,
    the newer one supersedes the newly ingested doc.
    """
    trial_key = _pick_trial_key(record)
    if trial_key is None:
        return []  # orphan doc — can't do version resolution

    primary_type = record.classes[0].class_name.value

    # Find current (non-superseded) docs of the same type in the same trial
    rows = client.query(
        "find_version_match",
        {"doc_type": primary_type, "trial_id": trial_key},
    )
    if not rows:
        return []

    doc_id = record.raw_sha256[:16]
    new_ordinal = record.version_ordinal
    new_version = record.version

    matches: list[VersionMatch] = []

    for row in rows:
        existing_id = row["doc.doc_id"]

        # Skip if same document (content hash match)
        if existing_id == doc_id:
            continue

        existing_ordinal = row.get("doc.version_ordinal")
        existing_version = row.get("doc.version")

        if _is_newer(new_ordinal, existing_ordinal, new_version, existing_version):
            matches.append(VersionMatch(
                superseded_doc_id=existing_id,
                superseder_doc_id=doc_id,
                reason=f"{primary_type} {new_version} supersedes {existing_version}",
                direction="forward",
            ))
        elif _is_newer(existing_ordinal, new_ordinal, existing_version, new_version):
            matches.append(VersionMatch(
                superseded_doc_id=doc_id,
                superseder_doc_id=existing_id,
                reason=f"{primary_type} {existing_version} supersedes {new_version}",
                direction="reverse",
            ))

    return matches


def _is_newer(
    new_ord: int | None,
    old_ord: int | None,
    new_str: str | None,
    old_str: str | None,
) -> bool:
    """Is *new* a later version than *old*?

    Prefers version_ordinal (integer comparison). Falls back to numeric
    dot-separated string parsing, then raw string comparison.
    """
    # Prefer ordinals — reliable, LLM-normalized
    if new_ord is not None and old_ord is not None:
        return new_ord > old_ord

    # Fallback to string-based comparison
    if new_str is None or old_str is None:
        return False

    try:
        new_parts = [int(x) for x in new_str.replace("v", "").split(".")]
        old_parts = [int(x) for x in old_str.replace("v", "").split(".")]
        return new_parts > old_parts
    except (ValueError, AttributeError):
        return new_str > old_str
