# CLAUDE.md — Clinical Picasso Hackathon Bible

> This is the single source of truth for the hackathon. Every architectural and product
> decision must trace back to something on this page. If reality drifts from this doc,
> update the doc first, then the code.

---

## 1. The Brief (verbatim, from Biorce)

- **Company:** Biorce — biorce.com
- **Tagline:** "Building defensible AI solutions on one of the world's largest real-world datasets."
- **Track:** The Library of Babel — AI Edition (Challenge I)

**Provocation (the question we are answering):**
> Can AI agents bring order to the chaos of clinical documentation — finding, linking,
> classifying, and surfacing the right document at the right moment?

**Context (why this matters to Biorce right now):**
> Clinical trials generate an overwhelming volume of documents — protocols, amendments,
> informed consents, regulatory submissions, site files — scattered across teams, systems,
> and geographies. At Biorce, we believe that a smart, centralised document backbone is
> foundational to running faster and more compliant trials. We want to see what's possible
> when you reimagine document management from the ground up.

**The one thing a winning solution MUST demonstrate:**
> Intelligent document organisation and retrieval — showing how **structure, metadata,
> versioning, and linkage** can be **automated or augmented** to meaningfully reduce
> manual overhead and human error.

**Teaser / canonical demo scenario:**
> "Somewhere in your system live **47 related documents** — consents, site instructions,
> regulatory filings — each of which **may now be outdated**. You have **48 hours before
> your next audit**. Can your platform **find them all, flag what's changed, and tell you
> exactly what needs to be updated**?"

**Resources Biorce is providing:**
- Sandbox with API and AI models to integrate
- Cloud resources if needed
- Licenses activated via team member emails (pre-event setup)
- Data/credits/tools: TBD — **ask organizers on arrival**

**Prize:**
- Private lunch with Biorce engineering leaders
- A day working alongside their AI/ML team on real-world challenges
- Professional photoshoot
- €250 Amazon voucher per team member
- (No runner-up prize)

---

## 2. The Problem, Specified (so we never lose focus)

### 2.1 The four verbs the judges will score us on

Any feature we build must serve one of these. If it doesn't, cut it.

1. **FIND** — locate all documents relevant to a query/event across scattered sources
2. **LINK** — discover and surface relationships between documents (parent/child,
   supersedes, references, derived-from, governs, depends-on)
3. **CLASSIFY** — assign type, status, owner, site/country, version, lifecycle stage,
   and structured metadata automatically
4. **SURFACE** — present the right document/answer at the right moment for the user's
   task (audit prep, amendment rollout, site activation, etc.)

The brief literally says "finding, linking, classifying, and surfacing" — this is
the rubric. Mirror it in the UI and the pitch.

### 2.2 The canonical demo = the "47 documents" scenario

This is our **acceptance test**. The system must, end-to-end:

| Step | Input | Expected output |
|------|-------|-----------------|
| 1 | A triggering change (e.g. protocol v2.1 → v2.2 amendment ingested) | System identifies the change and its semantic delta |
| 2 | The change + the corpus | The **exact set of downstream documents** that are now stale, linked with *why* each is affected |
| 3 | Per affected document | A specific, actionable instruction: what field/section/signature/version needs to change, who owns it, and a suggested edit where possible |
| 4 | Whole set | An **audit-ready report** — grouped by site, country, document type, urgency — exportable and defensible |

If we can walk a judge through this flow on a realistic corpus with a plausible
"47 docs" output, we have a winning demo. Everything else is scaffolding.

### 2.3 The three pillars the MUST-demo requires

The brief names them explicitly — treat them as first-class features, not side effects:

- **Structure** — canonical taxonomy of document types and fields (see §3.2)
- **Metadata** — extracted, validated, queryable (not just tags — typed fields)
- **Versioning** — documents as lineages, not files; diffs, supersession, effective dates
- **Linkage** — explicit, typed edges between documents (a graph, not a folder tree)

---

## 3. Clinical Trial Domain Primer (what Biorce will assume we know)

We are being judged by clinical-trial insiders. Getting the domain vocabulary right
signals that our solution is real, not a generic RAG demo.

### 3.1 Governing frameworks (name-drop only as needed)

- **ICH-GCP E6(R3)** — Good Clinical Practice, the global standard for running trials.
  Defines what "essential documents" are and the sponsor/investigator split.
- **TMF Reference Model** (DIA) — the de-facto canonical taxonomy for the Trial Master
  File. ~250 document types organized into 11 zones. **If we need a document ontology
  out of the box, this is it.**
- **21 CFR Part 11** (US FDA) — electronic records and signatures requirements.
  Relevant for audit trail, e-signatures, data integrity claims.
- **EU CTR (Regulation 536/2014)** — EU clinical trial regulation, CTIS submissions.
- **HIPAA / GDPR** — patient data handling; our demo should avoid real PHI/PII.

### 3.2 Document types that MUST appear in our demo corpus

These are the documents the teaser explicitly names plus the ones that make the
linkage story credible:

- **Protocol** + **Protocol Amendments** (the trigger of most cascading changes)
- **Informed Consent Form (ICF)** — usually exists as: master ICF → country-adapted →
  site-adapted → subject-signed. This is the classic "47 docs" multiplier.
- **Investigator Brochure (IB)** — safety/efficacy reference; amended over time
- **Regulatory submissions / approvals** — IND/CTA, IRB/IEC approvals, CTIS filings
- **Site files** — FDA 1572, CVs, delegation of authority log, training records,
  financial disclosures
- **Monitoring reports / visit reports**
- **Safety documents** — SAE reports, SUSARs, DSUR
- **Site instructions / site activation letters / memos**
- **Vendor agreements, CDAs, lab manuals**

### 3.3 The cascade that makes this problem real

This is *why* one protocol amendment can invalidate 47 documents. Commit it to memory:

```
Protocol v2.1 → v2.2
    ├── Master ICF must be updated (new risks, new procedures)
    │     ├── Country ICFs (×N countries) must be re-translated / re-approved
    │     │     └── Site ICFs (×M sites/country) must be re-issued
    │     │           └── Subject consents may need to be re-obtained
    ├── IRB/IEC approvals must be re-filed per site
    ├── Regulatory submissions (IND amendment / CTA substantial mod) required
    ├── Investigator Brochure references may be stale
    ├── Site training materials must be updated and re-delivered
    ├── Delegation logs / 1572s may need updating if procedures changed
    ├── Monitoring plan / CRF / source doc templates may change
    └── Lab manuals, pharmacy manuals may need version bumps
```

A good solution *traces this cascade automatically*. A great solution also tells you
**which nodes are safe to skip** (e.g. administrative-only amendments that don't
trigger ICF re-consent).

### 3.4 Metadata that actually matters (for extraction targets)

Prioritize these fields when doing structured extraction — they unlock every
linkage and every query:

- `document_type` (map to TMF Reference Model where possible)
- `protocol_id` / `study_id` / `sponsor`
- `version` + `effective_date` + `supersedes` (→ version lineage)
- `country` + `site_id` + `investigator_name`
- `language`
- `signatories` (role, name, date — proxy for "is this finalized?")
- `references_to` (explicit mentions of other docs — IDs, titles, versions)
- `regulatory_citations` (e.g. "per Protocol §7.2", "per ICH-GCP 4.8")
- `status` (draft / approved / active / superseded / archived)
- `expiration_or_review_date` (critical for audit readiness)

---

## 4. Architectural Stance (default choices; deviate only with reason)

### 4.1 Shape of the system

A **hybrid agentic RAG + knowledge graph**, not pure vector search:

- **Ingestion pipeline** — parse (PDF/DOCX/scans), OCR if needed, chunk semantically
  by section, extract metadata into typed fields.
- **Knowledge graph** — nodes are documents + document lineages; edges are typed
  (SUPERSEDES, REFERENCES, GOVERNS, DERIVED_FROM, APPROVED_BY, APPLIES_TO_SITE).
  The graph is what makes linkage explainable to auditors.
- **Vector index** — over chunks, for semantic retrieval and cross-doc similarity
  (used to *discover* linkages the graph doesn't know yet).
- **Agent layer** — orchestrates FIND/LINK/CLASSIFY/SURFACE. Multi-agent only if it
  makes the demo clearer; otherwise a single orchestrator + tools is faster to ship.
- **Change-detection engine** — diff between versions at semantic level (not line-diff),
  so "the risk section changed" is the output, not "line 412 differs."
- **Impact / cascade analyzer** — given a changed node, traverse the graph to emit
  the list of affected documents with a reason per edge.

### 4.2 Why this shape vs. alternatives

- **Pure RAG** loses linkage and versioning — the exact things the brief demands.
- **Pure graph** loses the fuzzy "this paragraph looks like it's about the new
  exclusion criterion" retrieval the demo needs.
- **Hybrid** lets us show judges both: a deterministic, explainable audit trail
  (graph) and an AI-powered discovery layer (vectors + LLM agents).

### 4.3 What earns points beyond correctness

- **Explainability** — every flagged document must come with *why* (which edge,
  which clause, which diff). Auditors don't trust black boxes.
- **Confidence / uncertainty** — flag low-confidence links for human review rather
  than silently being wrong. This is a regulated domain; humility wins.
- **Audit trail** — every system action logged with timestamp, input, output, model
  version. This maps directly to 21 CFR Part 11 talking points.
- **Round-trip-able output** — the "here's what needs updating" report should be
  exportable (CSV / JSON / PDF) and filterable by site/country/owner.

---

## 5. Demo Script (what we actually show on stage)

Keep the narrative tight. Target 3–4 minutes.

1. **Setup (20 sec):** "It's Monday. Your next audit is Wednesday. Your sponsor just
   issued Protocol Amendment v2.2. How many documents are now stale? You don't know."
2. **Ingest (30 sec):** Drop the amendment into the platform. Show auto-classification,
   metadata extraction, version-linking to v2.1.
3. **Diff (30 sec):** Show the semantic diff — not line diff. "Exclusion criterion
   added. Visit 4 procedure changed. New AE reporting threshold."
4. **Cascade (60 sec):** One click → the 47 affected documents, grouped by type and
   site, each with a specific reason. Show at least one link the user would have
   *missed manually* (e.g. a site instruction memo that cites the old procedure).
5. **Action (45 sec):** Generate the audit-prep report. Show a proposed redline on
   one ICF. Export.
6. **Close (15 sec):** "Structure, metadata, versioning, linkage — automated.
   Manual overhead gone. Audit-ready in minutes."

Every beat maps to one of the four verbs. If a feature doesn't fit this script,
it shouldn't ship for the demo.

---

## 6. Open Questions (resolve on day 1)

These gate real decisions — do not guess.

- [ ] **Sandbox scope:** which Biorce APIs / models exactly? Rate limits? Model IDs?
- [ ] **Data:** does Biorce provide a synthetic TMF corpus, or do we assemble one?
      (Backup: the TMF Reference Model site has sample docs; CTTI / public registries
      have real anonymized protocols.)
- [ ] **Cloud:** are credits provided? Preferred stack (AWS/GCP/Azure)?
- [ ] **Submission format:** demo video? Live? Repo? Slides? Deadline time?
- [ ] **Team size / roles** — who owns ingestion, graph, agents, UI, pitch?
- [ ] **Licenses:** have the team emails been submitted for license activation?

---

## 7. Non-Negotiables (rules we hold the line on)

- **No real PHI/PII.** Synthetic or public data only.
- **Every flagged link must be explainable.** No "the model said so" outputs.
- **Ship the demo scenario end-to-end before polishing any single component.**
  A walking skeleton beats a beautiful limb.
- **Use TMF Reference Model vocabulary** for document types wherever we can — it's
  the language the judges speak.
- **Hackathon posture:** optimize for the 3-minute demo and the judges' mental model,
  not for production robustness. But leave architecture hooks so "this could be real"
  is a defensible claim.

---

## 8. Quick Reference — Glossary

| Term | Meaning |
|------|---------|
| TMF | Trial Master File — the authoritative document set for a trial |
| eTMF | Electronic TMF (the SaaS category Biorce competes in) |
| ICF | Informed Consent Form |
| IB | Investigator Brochure |
| IRB / IEC | Institutional Review Board / Independent Ethics Committee |
| IND / CTA | Investigational New Drug (US) / Clinical Trial Application (EU/other) |
| CTIS | Clinical Trials Information System (EU portal under CTR) |
| SAE / SUSAR | Serious Adverse Event / Suspected Unexpected Serious Adverse Reaction |
| DSUR | Development Safety Update Report |
| CSR | Clinical Study Report |
| 1572 | FDA Form 1572 — investigator statement |
| GCP | Good Clinical Practice |
| Sponsor | The organization running the trial (pharma/biotech) |
| Site | A clinical location enrolling patients |
| Investigator | The physician responsible at a site (PI = Principal Investigator) |
