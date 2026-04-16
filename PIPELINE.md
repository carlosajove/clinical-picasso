# PIPELINE.md — Document Processing Pipeline

> Operational spec for the ingestion → graph → audit pipeline. Companion to `CLAUDE.md`.
> Last updated to match the actual implementation.

---

## Phases

| # | Phase              | Scope    | Parallel | Output                                                  | Entry point                        |
|---|--------------------|----------|----------|---------------------------------------------------------|------------------------------------|
| 1 | Preprocessing      | per-file | yes      | deduplicated, content-extracted `DocumentRecord`s       | `src/preprocessing.py`             |
| 2 | Extraction         | per-doc  | yes      | one `ExtractionRecord` per doc (cached on disk)         | `src/extraction/extract.py`        |
| 3 | Graph creation     | per-doc  | no       | Document + Trial nodes, BelongsToTrial edges            | `src/graph/serializer.py`          |
| 4 | Ingestion          | per-doc  | no       | version chains, typed edges, change reports             | `src/ingest/ingestion.py`          |
| 5 | Refinement         | global   | no       | reclassification, orphan connection, edge discovery     | `src/ingest/refinement.py`         |
| 6 | Audit              | global   | no       | inconsistency flags + audit report                      | `src/cascade/inconsistency_checker.py` |

Phases 1–2 are embarrassingly parallel. Phases 3–6 operate against the shared graph.

The main orchestrator (`main.py`) currently runs Phases 1–2. Phases 3–6 are invoked
through `ingest()` and the refinement/audit modules.

---

## Phase 1 — Preprocessing

**Module:** `src/preprocessing.py`
**Class:** `Preprocessing`

Loads all files from `data/`, deduplicates, and extracts text content.

| Step | Method | What it does |
|------|--------|--------------|
| 1 | `load_all()` | Walks `data/` recursively; builds a `DocumentRecord` per file (filename, size, SHA-256, raw bytes) |
| 2 | `deduplicate()` | Exact dedup by SHA-256 content hash |
| 3 | `deduplicate_near()` | Near-duplicate detection via TF-IDF cosine similarity + file-size ratio (sklearn) |
| 4 | `extract_content()` | Dispatches by file type: PDF (PyMuPDF/fitz), DOCX (python-docx), HTML (BeautifulSoup), TXT/MD/CSV (raw read) |

**Output:** list of `DocumentRecord(filename, size, sha256, raw_bytes, content)`.

**Supported formats:** PDF, DOCX, TXT, MD, CSV, HTML.

---

## Phase 2 — Extraction (parallel, per-doc)

**Modules:** `src/extraction/extract.py`, `src/extraction/schema.py`, `src/extraction/prompt.py`, `src/extraction/cache.py`
**Class:** `DocumentExtractor`

One LLM call per document. A pydantic-ai `Agent` wrapping **Claude Sonnet 4.5** produces
a structured `ExtractionRecord` constrained to the Pydantic schema.

**Extracted fields (per `LLMExtraction`):**

| Field | Type | Notes |
|-------|------|-------|
| `classes` | `list[ClassCandidate]` | Ranked candidates, each with `doc_class`, `reasoning`, `confidence` [0,1] |
| `nct_id` | `str?` | ClinicalTrials.gov identifier |
| `eudract_id` | `str?` | EU Clinical Trials Register ID |
| `eu_ct_id` | `str?` | EU CT number |
| `sponsor_protocol_id` | `str?` | Sponsor's internal protocol ID |
| `version` | `str?` | Document version string |
| `country` | `str?` | ISO country |
| `site_id` | `str?` | Site identifier |
| `references_to` | `list[str]` | Raw citation strings (resolved in Phase 4) |

**Document classes** (12 categories in `DocumentClass` enum):

| Code | Meaning |
|------|---------|
| `CSP` | Clinical Study Protocol |
| `IB` | Investigator Brochure |
| `ICF` | Informed Consent Form |
| `CRF` | Case Report Form |
| `CSR` | Clinical Study Report |
| `eTMF` | Electronic TMF document (catch-all regulated) |
| `REGULATORY_GOVERNANCE` | SmPC, DSUR, DSMB Charter |
| `SYNOPSIS` | Protocol synopsis |
| `PATIENT_QUESTIONNAIRE` | PROs, surveys |
| `INFO_SHEET` | Patient information (non-consent, non-questionnaire) |
| `MEDICAL_PUBLICATION` | Published literature |
| `NOISE` | Not a trial document |

**Caching:** Results are persisted as JSON in `out/records/{sha256}.json`. Re-runs
skip documents that already have a cached record.

**Concurrency:** async with `CONCURRENCY = 4` (configurable in `main.py`).

---

## Phase 3 — Graph creation

**Modules:** `src/graph/serializer.py`, `src/graph/client.py`

Materializes extraction records into the OmniGraph knowledge graph.

**Graph database:** OmniGraph (CLI-driven; invoked via subprocess in `OmniGraphClient`).
**Schema:** `schema/clinical.pg`

### Nodes

| Node type | Key | Notable fields |
|-----------|-----|----------------|
| **Document** | `doc_id` | `source_file`, `content_hash`, `document_type`, `classification_confidence`, `raw_classes` (JSON), `version`, `status`, `country`, `site_id`, `summary`, `sponsor_name`, `sponsor_protocol_id`, `trial_title`, `intervention`, `indication`, `phase` |
| **Trial** | `trial_key` | `nct_id`, `eudract_id`, `eu_ct_id`, `isrctn_id`, `utn_id`, `ind_number`, `cta_number`, `sponsor_name`, `acronym`, `therapeutic_area`, `title`, `phase`, `intervention`, `indication` |

### Edges

| Edge type | Direction | Data fields | Meaning |
|-----------|-----------|-------------|---------|
| **BelongsToTrial** | Document → Trial | — | Document is part of this trial |
| **Supersedes** | Document → Document | `reason` | Newer version replaces older |
| **DerivedFrom** | Document → Document | `derivation_type` | Adaptation hierarchy (site/country/protocol) |
| **References** | Document → Document | `citation_text` | Explicit textual citation |
| **Governs** | Document → Document | `authority_type` | Regulatory/governance authority |

**Serialization:** `serialize_document()`, `serialize_trial()`, `serialize_belongs_to_trial()`
convert an `ExtractionRecord` into JSONL lines that OmniGraph loads.

**Trial ID resolution priority:** `sponsor_protocol_id` > `nct_id` > `eudract_id` > `eu_ct_id`.

---

## Phase 4 — Ingestion (per-doc, against the graph)

**Module:** `src/ingest/ingestion.py`
**Function:** `ingest(record, client) → IngestResult`

Each document is ingested one at a time against the live graph. The function:

1. **Loads** the Document node and Trial node (if a trial ID exists).
2. **Checks for existing duplicates** by content hash (skips if already present).
3. **Resolves versions** — `src/ingest/version_resolver.py::resolve_version()` detects
   if the new document supersedes an existing one in the same trial + document type.
   Compares numeric version strings (e.g. 2.2 > 2.1). Creates **Supersedes** edges and
   marks older docs with `status = "superseded"`.
4. **Discovers edges** — `src/ingest/linker.py` runs three deterministic passes:
   - `_discover_references()`: matches raw citation strings from `references_to[]` against
     existing documents by source filename or document type.
   - `_discover_derived_from()`: ICF-specific adaptation cascade — site ICF → country ICF
     → master ICF → CSP, inferred from `site_id` and `country` metadata. Creates
     **DerivedFrom** edges with `derivation_type` (site_adaptation, protocol_derivation).
   - `_discover_governs()`: regulatory/governance linking (implementation placeholder).
5. **Optionally refines classification** — `src/ingest/classifier.py` checks if the top
   two class candidates are within 0.15 confidence of each other (`needs_refinement()`).
   If so, `build_refinement_context()` queries the graph for the trial's document-type
   distribution to inform a reclassification pass.
6. **Returns** an `IngestResult` with a change report listing all nodes/edges created.

---

## Phase 5 — Refinement (global sweep)

**Module:** `src/ingest/refinement.py`
**Function:** `run_refinement(client) → RefinementResult`

An idempotent five-step sweep meant to run after a batch of ingestions. Catches
relationships that were impossible to detect at single-document ingestion time
(e.g. a parent document that was ingested after its child).

| Step | What | Status |
|------|------|--------|
| 1 | **Reclassify low-confidence docs** (confidence < 0.6) | Identifies candidates; full re-LLM deferred |
| 2 | **Connect orphans** — find docs with zero edges | Identifies orphans for re-linking in step 3 |
| 3 | **Discover missing edges** — re-run linker for all docs | Framework in place; catches late-arriving parents |
| 4 | **Resolve trial duplicates** — fuzzy title matching | Logs candidates; exact match only currently |
| 5 | **Validate existing edges** — re-check low-confidence links | Placeholder |

**Output:** `RefinementResult(reclassified, orphans_connected, new_edges, trials_merged, edges_validated)`.

---

## Phase 6 — Audit & impact analysis

**Modules:** `src/cascade/inconsistency_checker.py`, `src/cascade/report_generator.py`

### Inconsistency checks

`check_all(client) → AuditReport` runs eight checks via OmniGraph queries:

| # | Check | Query file | What it flags |
|---|-------|------------|---------------|
| 1 | Stale parents | `inconsistencies.gq::stale_parents` | Doc derives from a superseded parent |
| 2 | Stale references | `inconsistencies.gq::stale_references` | Doc references a superseded doc |
| 3 | Stale governance | `inconsistencies.gq::stale_governance` | Governance doc points to superseded doc |
| 4 | Orphan documents | `orphans.gq::find_orphans` | Docs with zero inbound or outbound edges |
| 5 | Low confidence | `orphans.gq::low_confidence` | Classification confidence < 0.6 |
| 6 | Missing doc types | (in-code logic) | Trial missing expected types (CSP, ICF, IB) |
| 7 | Version gaps | (in-code logic) | e.g. v1.0 and v3.0 exist but no v2.0 |
| 8 | Metadata conflicts | (in-code logic) | Docs in same trial with different sponsor/phase |

### Impact / cascade analysis

**Queries:** `queries/cascade.gq`

Given a changed document, traverses typed edges up to 10 hops:

- `cascade_derived(doc_id)` — all docs downstream via DerivedFrom
- `cascade_references(doc_id)` — all docs that reference this one
- `cascade_governed(doc_id)` — all docs governed by this one

Excludes already-superseded nodes. Returns affected document IDs + metadata.

### Audit report

`AuditReport` contains a list of issues, each with `severity`, `category`, `doc_id`,
`description`, and `details`. Exportable as JSON.

---

## Query layer

### Stored queries (`queries/`)

| File | Purpose | Key queries |
|------|---------|-------------|
| `mutations.gq` | CRUD | `add_document`, `add_trial`, `add_belongs_to_trial`, `add_supersedes`, `add_derived_from`, `add_references`, `add_governs`, `mark_superseded` |
| `match_existing.gq` | Lookups | `find_version_match`, `find_trial`, `find_trial_by_nct`, `find_doc_by_hash` |
| `inconsistencies.gq` | Audit | `stale_parents`, `stale_references`, `stale_governance`, `superseded_documents`, `current_documents` |
| `cascade.gq` | Impact | `cascade_derived`, `cascade_references`, `cascade_governed` |
| `orphans.gq` | Cleanup | `find_orphans`, `low_confidence` |
| `audit.gq` | Reporting | Audit-specific aggregations |

### Natural language query interface

**Module:** `src/chat/query_gen.py`

A pydantic-ai Agent reads the graph schema + a natural language question, generates a
`.gq` query, executes it against the graph, and retries once with error feedback if the
first attempt fails. Returns `QueryResult(question, gq_query, explanation, rows, error)`.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| LLM | Claude Sonnet 4.5 via pydantic-ai |
| Graph DB | OmniGraph (CLI, JSONL snapshots) |
| Schema validation | Pydantic v2.8+ |
| Agent framework | pydantic-ai v0.3+ |
| PDF parsing | PyMuPDF (fitz), pypdf |
| DOCX parsing | python-docx |
| HTML parsing | BeautifulSoup4 |
| Near-dup detection | scikit-learn TF-IDF + cosine similarity |
| PDF generation | fpdf2 |
| Config | python-dotenv (.env) |

---

## Not yet implemented

These are planned in `CLAUDE.md` but not present in the codebase:

- **Phase 5.4 — Approval linking:** approval letters → protocol version they authorize.
- **Phase 5.5 — Fuzzy inference:** vector similarity within a trial to propose candidate
  links for docs without explicit citations, confirmed by a short LLM call. O(N*K).
- **Vector index / embedding store:** no embedding calls or vector DB integration yet.
- **Semantic diff engine:** section-level diff between document versions (currently
  version chains are detected but content diffs are not computed).
- **UI / frontend:** the system is backend-only; no web interface exists.
- **Multi-agent orchestration:** single-agent LLM calls only; no agent-to-agent routing.
- **Full refinement re-LLM calls:** refinement steps 1, 4, 5 identify candidates but
  don't yet invoke the LLM for reclassification or edge validation.

---

## Invariants

- One node per logical document version. Multi-label uncertainty lives as a field (`raw_classes`), not as extra nodes.
- Linkage stays within a trial partition.
- Deterministic linkage (version chains, citations, adaptation cascade) runs before any fuzzy inference.
- Failures flag to audit issues; never silently dropped.
- No real PHI/PII in the corpus.
- Extraction results are cached by content hash — re-processing the same file is a no-op.
