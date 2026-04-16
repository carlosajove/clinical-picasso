"""Detect whether a new document supersedes an existing one in the graph."""

from __future__ import annotations

from dataclasses import dataclass

from src.extraction.schema import ExtractionRecord
from src.graph.client import OmniGraphClient
from src.graph.serializer import _pick_trial_key


@dataclass
class VersionMatch:
    """Result of version resolution."""
    superseded_doc_id: str
    reason: str


def resolve_version(
    record: ExtractionRecord,
    client: OmniGraphClient,
) -> VersionMatch | None:
    """Check if *record* is a newer version of a document already in the graph.

    Returns a VersionMatch if a superseded doc is found, else None.
    """
    trial_key = _pick_trial_key(record)
    if trial_key is None:
        return None  # orphan doc — can't do version resolution

    primary_type = record.classes[0].class_name.value

    # Find current (non-superseded) docs of the same type in the same trial
    rows = client.query(
        "find_version_match",
        {"doc_type": primary_type, "trial_id": trial_key},
    )
    if not rows:
        return None

    new_version = record.version
    if new_version is None:
        return None  # can't determine ordering without a version string

    for row in rows:
        existing_version = row.get("doc.version")
        existing_id = row["doc.doc_id"]

        # Skip if same document (content hash match)
        if existing_id == record.raw_sha256[:16]:
            continue

        if existing_version is None:
            # Existing doc has no version — ambiguous, skip
            continue

        if _is_newer(new_version, existing_version):
            return VersionMatch(
                superseded_doc_id=existing_id,
                reason=f"{primary_type} {new_version} supersedes {existing_version}",
            )

    return None


def _is_newer(new: str, old: str) -> bool:
    """Heuristic: is *new* a later version than *old*?

    Tries numeric comparison first (2.2 > 2.1), falls back to
    string comparison.
    """
    try:
        new_parts = [int(x) for x in new.replace("v", "").split(".")]
        old_parts = [int(x) for x in old.replace("v", "").split(".")]
        return new_parts > old_parts
    except (ValueError, AttributeError):
        return new > old
