"""Deterministic edge discovery — no LLM calls.

Given a newly ingested document and the current graph state, discover
edges (DerivedFrom, References, Governs) using structured metadata rules.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.extraction.schema import ExtractionRecord
from src.graph.client import OmniGraphClient
from src.graph.serializer import _pick_trial_key


@dataclass
class DiscoveredEdge:
    """An edge to create."""
    edge_type: str       # mutation name in mutations.gq
    params: dict         # params for the mutation


def discover_edges(
    record: ExtractionRecord,
    client: OmniGraphClient,
) -> list[DiscoveredEdge]:
    """Return edges to create for *record* based on deterministic rules."""
    edges: list[DiscoveredEdge] = []
    doc_id = record.raw_sha256[:16]
    trial_key = _pick_trial_key(record)
    primary_type = record.classes[0].class_name.value

    if trial_key is not None:
        edges.extend(_discover_derived_from(doc_id, primary_type, record, client, trial_key))
        edges.extend(_discover_references(doc_id, record, client))
        edges.extend(_discover_governs(doc_id, primary_type, record, client, trial_key))

    return edges


def _discover_derived_from(
    doc_id: str,
    doc_type: str,
    record: ExtractionRecord,
    client: OmniGraphClient,
    trial_key: str,
) -> list[DiscoveredEdge]:
    """ICF derivation cascade: Site ICF → Country ICF → Master ICF → CSP."""
    if doc_type != "ICF":
        return []

    edges = []

    # Site ICF (has site_id) → Country ICF (has country, no site_id)
    if record.site_id and record.country:
        rows = client.query(
            "find_version_match",
            {"doc_type": "ICF", "trial_id": trial_key},
        )
        for row in rows:
            if row["doc.doc_id"] == doc_id:
                continue
            # A country-level ICF: look for docs in the same trial
            # that we can check country/site against.
            # For now, connect to any existing ICF in the same trial
            # that doesn't have a site_id (i.e., is a higher-level ICF).
            # This is a heuristic — the refinement sweep can fix errors.
            edges.append(DiscoveredEdge(
                edge_type="add_derived_from",
                params={
                    "child_id": doc_id,
                    "parent_id": row["doc.doc_id"],
                    "derivation_type": "site_adaptation",
                },
            ))
            break  # link to the first match

    # Master ICF (no site_id, no country) → CSP
    if not record.site_id and not record.country:
        rows = client.query(
            "find_version_match",
            {"doc_type": "CSP", "trial_id": trial_key},
        )
        for row in rows:
            edges.append(DiscoveredEdge(
                edge_type="add_derived_from",
                params={
                    "child_id": doc_id,
                    "parent_id": row["doc.doc_id"],
                    "derivation_type": "protocol_derivation",
                },
            ))
            break

    return edges


def _discover_references(
    doc_id: str,
    record: ExtractionRecord,
    client: OmniGraphClient,
) -> list[DiscoveredEdge]:
    """Match raw citation strings from references_to against existing docs."""
    if not record.references_to:
        return []

    edges = []
    all_docs = client.query("all_documents")

    for citation in record.references_to:
        citation_lower = citation.lower()
        for row in all_docs:
            target_id = row["doc.doc_id"]
            if target_id == doc_id:
                continue
            # Simple heuristic: check if the source_file or doc_type
            # appears in the citation string
            source_file = row.get("doc.source_file", "").lower()
            doc_type = row.get("doc.document_type", "").lower()
            version = row.get("doc.version") or ""

            if source_file and source_file in citation_lower:
                edges.append(DiscoveredEdge(
                    edge_type="add_references",
                    params={
                        "from_id": doc_id,
                        "to_id": target_id,
                        "citation_text": citation,
                    },
                ))
                break
            if doc_type in citation_lower and version and version in citation:
                edges.append(DiscoveredEdge(
                    edge_type="add_references",
                    params={
                        "from_id": doc_id,
                        "to_id": target_id,
                        "citation_text": citation,
                    },
                ))
                break

    return edges


def _discover_governs(
    doc_id: str,
    doc_type: str,
    record: ExtractionRecord,
    client: OmniGraphClient,
    trial_key: str,
) -> list[DiscoveredEdge]:
    """Regulatory/governance docs govern CSPs and ICFs in the same trial."""
    governance_types = {"eTMF", "SmPC / DSUR / DSMB Charter"}
    if doc_type not in governance_types:
        return []

    edges = []
    # Find CSPs and ICFs in the same trial
    for target_type in ["CSP", "ICF"]:
        rows = client.query(
            "find_version_match",
            {"doc_type": target_type, "trial_id": trial_key},
        )
        for row in rows:
            edges.append(DiscoveredEdge(
                edge_type="add_governs",
                params={
                    "gov_id": doc_id,
                    "doc_id": row["doc.doc_id"],
                    "authority_type": doc_type,
                },
            ))

    return edges
