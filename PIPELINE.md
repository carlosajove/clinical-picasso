# PIPELINE.md — Document Processing Pipeline

> Operational spec for the ingestion → graph pipeline. Companion to `CLAUDE.md`.
> If reality drifts, update this doc first, then the code.

---

## Phases

| # | Phase          | Scope    | Parallel | Output                                     |
|---|----------------|----------|----------|--------------------------------------------|
| 1 | Preprocessing  | per-file | yes      | normalized, segmented, hashed docs         |
| 2 | Ingestion      | per-doc  | yes      | one structured extraction record per doc   |
| 3 | Graph creation | global   | no       | document nodes materialized                |
| 4 | Entities       | global   | no       | trial nodes, doc→trial membership, dedup   |
| 5 | Verification   | global   | no       | inferred links + conflict flags            |

Phases 1–2 are embarrassingly parallel. Phases 3–5 need the whole corpus.

---

## Phase 1 — Preprocessing
Normalize (PDF/DOCX → text + structure), OCR when needed, segment composite files into logical documents, hash content, chunk for the vector index.

## Phase 2 — Ingestion (parallel, per-doc)
One LLM call per logical doc, JSON-constrained. Extract classification (with candidate alternatives for ambiguous docs), all trial identifiers, version metadata, scope (country/site/language), status, and raw citation strings. Validate identifiers by regex after the call.

## Phase 3 — Graph creation
Materialize document nodes from extraction records. Docs are "floating" at this point — trial membership is assigned in Phase 4.

## Phase 4 — Entities
Cluster identifiers that co-occur on the same doc → one trial per cluster. Attach docs to trials via an identifier index. Dedup by content hash / tight metadata match; never merge across differing version/country/site/language. Commit classification when confidence is high; flag ambiguous cases for Phase 5.

## Phase 5 — Verification (layered, cheapest first)
Where the "47 docs" demo is earned. Run in order; don't invert.

1. **Resolve citations** — raw citation strings from Phase 2 bind to concrete trial docs. Unresolvable → flag.
2. **Version chains** — order docs by version/date within each class; link consecutive versions. Gaps → flag.
3. **Adaptation cascade** — for hierarchical classes (canonically the ICF: master → country → site), link top-down by metadata. Downstream lagging master → stale flag.
4. **Approvals** — approval letters link to the protocol version they authorize. Older-than-current → flag.
5. **Fuzzy inference (ship last)** — vector similarity within a trial proposes candidate links for docs without explicit citations; a short LLM call confirms. Keep calls O(N·K).
6. **Conflict surfacing** — dangling citations, broken chains, stale adaptations, stale approvals, missing expected children — visible as flags in the UI.

---

## Invariants

- One node per logical document version. Multi-label uncertainty lives as a field, not as extra nodes.
- Linkage stays within a trial partition.
- Deterministic linkage (5.1–5.4) runs before fuzzy (5.5). Always.
- Failures flag to a review queue; never silently drop.
- No real PHI/PII.

---

## Open questions (decide before coding)

- Graph DB choice.
- Vector store choice.
- LLM provider (Biorce sandbox vs. direct API).
- Corpus source (synthetic TMF vs. Biorce-provided).
- Language coverage (EN-only vs. multilingual — the ICF cascade demo wants ≥2).
