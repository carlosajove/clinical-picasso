"""Graph endpoints — export and cascade analysis."""

from __future__ import annotations

from fastapi import APIRouter

from api.deps import get_client

router = APIRouter()


@router.get("/export")
def graph_export() -> list[dict]:
    """Export all graph nodes and edges as JSONL dicts."""
    client = get_client()
    return client.export()


@router.get("/cascade/{doc_id}")
def cascade_analysis(doc_id: str) -> dict:
    """Run cascade analysis for a document — returns derived, referenced, and governed docs."""
    client = get_client()
    query_file = str(client.queries_dir / "cascade.gq")

    derived = client.read(query_file, "cascade_derived", {"changed_id": doc_id})
    references = client.read(query_file, "cascade_references", {"changed_id": doc_id})
    governed = client.read(query_file, "cascade_governed", {"changed_id": doc_id})

    all_affected_ids = set()
    for row in derived + references + governed:
        doc = row.get("affected.doc_id") or row.get("$affected.doc_id")
        if doc:
            all_affected_ids.add(doc)

    return {
        "source_doc_id": doc_id,
        "derived": derived,
        "references": references,
        "governed": governed,
        "total_affected": len(all_affected_ids),
    }
