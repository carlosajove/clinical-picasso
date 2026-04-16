"""Semantic diff between two document versions.

Uses the LLM to produce a structured list of changes, not a line diff.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SemanticChange:
    """One meaningful change between two document versions."""
    section: str          # e.g. "Exclusion Criteria", "Visit 4 Procedures"
    change_type: str      # "added", "removed", "modified"
    description: str      # human-readable summary


@dataclass
class SemanticDiff:
    """The full diff between old and new versions."""
    old_doc_id: str
    new_doc_id: str
    changes: list[SemanticChange]
    summary: str          # 1-2 sentence overall summary


def compute_diff(
    old_summary: str | None,
    new_summary: str | None,
    old_doc_id: str,
    new_doc_id: str,
) -> SemanticDiff:
    """Compute a semantic diff from document summaries.

    For the hackathon, this uses the summaries extracted in Pass 1.
    A production version would compare full document content via LLM.
    """
    if not old_summary or not new_summary:
        return SemanticDiff(
            old_doc_id=old_doc_id,
            new_doc_id=new_doc_id,
            changes=[],
            summary="Unable to compute diff — missing summary for one or both versions.",
        )

    # Placeholder: in the full implementation, this would call the LLM with
    # both summaries and ask for a structured change list.
    # For now, produce a basic diff noting that the document was updated.
    return SemanticDiff(
        old_doc_id=old_doc_id,
        new_doc_id=new_doc_id,
        changes=[
            SemanticChange(
                section="General",
                change_type="modified",
                description=f"Document updated from {old_doc_id} to {new_doc_id}.",
            )
        ],
        summary=f"New version {new_doc_id} supersedes {old_doc_id}. Full semantic diff requires LLM analysis of document content.",
    )
