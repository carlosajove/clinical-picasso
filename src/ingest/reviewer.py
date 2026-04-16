"""LLM-powered reviewer agent — validates and corrects per-document during ingestion.

Runs once per document after deterministic steps (version resolution, edge discovery).
Uses graph context to:
  - Validate document classification
  - Detect amendments and identify their base documents
  - Suggest missing edges
  - Flag inconsistencies introduced by the new document
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from src.extraction.schema import ExtractionRecord
from src.graph.client import OmniGraphClient
from src.graph.serializer import _pick_trial_key
from src.ingest.classifier import needs_refinement, get_trial_type_distribution
from src.ingest.linker import detect_amendment_signal

log = logging.getLogger(__name__)

DEFAULT_MODEL = "anthropic:claude-sonnet-4-5"


# ---------- Output models ----------

class ReclassificationSuggestion(BaseModel):
    """Suggested reclassification for a document."""
    original_class: str
    suggested_class: str
    reasoning: str
    confidence: float = Field(ge=0, le=1)


class AmendmentDetection(BaseModel):
    """Whether this document is an amendment to an existing document."""
    is_amendment: bool
    amendment_label: str | None = None
    scope: str | None = None
    base_doc_id: str | None = None
    reasoning: str


class EdgeSuggestion(BaseModel):
    """A graph edge the reviewer thinks should be created."""
    edge_type: str
    from_doc_id: str
    to_doc_id: str
    reasoning: str
    params: dict = Field(default_factory=dict)


class ReviewVerdict(BaseModel):
    """Full output of the reviewer agent for one document."""
    classification_ok: bool
    reclassification: ReclassificationSuggestion | None = None
    amendment: AmendmentDetection
    suggested_edges: list[EdgeSuggestion] = Field(default_factory=list)
    inconsistencies: list[str] = Field(default_factory=list)
    reasoning: str


# ---------- System prompt ----------

REVIEWER_PROMPT = """\
You are a clinical trial document reviewer agent. Your job is to validate and correct
document classifications within a knowledge graph of clinical trial documents.

You receive:
1. A newly ingested document's metadata (classification, version, trial, phase, etc.)
2. The current state of the trial's document graph (what types exist, version chains, etc.)

Your tasks:

## Classification Validation
- Check if the assigned document type makes sense given the document's metadata and the
  trial context. For example, if a document's version string contains "Amendment", it
  should likely NOT be classified as a plain CSP (Clinical Study Protocol) — it is an
  amendment to a protocol.
- If classification is wrong, suggest the correct class from this vocabulary:
  CSP, IB, ICF, CRF, CSR, eTMF, SmPC / DSUR / DSMB Charter, Synopsis,
  Patient Questionnaire, Info Sheet, Medical Publications, NOISE

## Amendment Detection
This is critical. Detect if the document is a protocol amendment by checking:
- Version string contains "Amendment" (e.g., "Amendment 0.1 EU-1 (EU-specific)")
- Document is classified as CSP but references prior protocol versions
- The trial already has a base CSP and this looks like a modification

If it IS an amendment:
- Set is_amendment = true
- Extract the amendment_label from the version string (e.g., "Amendment 0.1 EU-1")
- Determine scope: "global" if no regional qualifier, otherwise extract it (e.g., "EU-specific")
- Identify the base_doc_id — the doc_id of the existing base CSP in the graph that this
  amendment modifies. Use the graph context provided. If no base CSP exists, set to null.

## Edge Suggestions
Suggest edges that the deterministic linker may have missed. Only suggest edges between
documents that exist in the graph (use the doc_ids from the context).
Valid edge types: DerivedFrom, References, Governs, Amends

## Inconsistency Detection
Flag issues like:
- Phase mismatch (document says Phase 2 but trial's other docs say Phase 3)
- Metadata conflicts (different sponsor names within same trial)
- A document that looks like it belongs to a different trial

Be precise and concise. Only flag real problems, not hypothetical ones.
Return your analysis as structured JSON matching the ReviewVerdict schema.
"""


# ---------- Context assembly ----------

def _build_review_context(
    record: ExtractionRecord,
    client: OmniGraphClient,
) -> str:
    """Assemble graph context for the reviewer agent."""
    doc_id = record.raw_sha256[:16]
    trial_key = _pick_trial_key(record)
    primary = record.classes[0]

    sections = []

    # Document metadata
    sections.append("## New Document")
    sections.append(f"- doc_id: {doc_id}")
    sections.append(f"- filename: {record.filename}")
    sections.append(f"- classified as: {primary.class_name.value} (confidence: {primary.confidence:.2f})")
    if len(record.classes) > 1:
        alt = record.classes[1]
        sections.append(f"- second candidate: {alt.class_name.value} (confidence: {alt.confidence:.2f}, reasoning: {alt.reasoning})")
    sections.append(f"- version: {record.version or 'not specified'}")
    sections.append(f"- phase: {record.phase or 'not specified'}")
    sections.append(f"- country: {record.country or 'not specified'}")
    sections.append(f"- site_id: {record.site_id or 'not specified'}")
    sections.append(f"- sponsor_protocol_id: {record.sponsor_protocol_id or 'not specified'}")
    sections.append(f"- sponsor_name: {record.sponsor_name or 'not specified'}")
    if record.summary:
        sections.append(f"- summary: {record.summary}")
    if record.references_to:
        sections.append(f"- references_to: {json.dumps(record.references_to)}")

    # Refinement signals
    sections.append("")
    sections.append("## Signals")
    sections.append(f"- needs_refinement (ambiguous classification): {needs_refinement(record)}")
    sections.append(f"- amendment_signal (version contains 'amendment'): {detect_amendment_signal(record)}")

    # Trial context
    if trial_key is not None:
        sections.append("")
        sections.append(f"## Trial Context (protocol_id: {trial_key})")

        distribution = get_trial_type_distribution(client, trial_key)
        if distribution:
            sections.append("Document type distribution:")
            for doc_type, count in sorted(distribution.items()):
                sections.append(f"  - {doc_type}: {count}")

        # Current documents in the trial
        try:
            trial_docs = client.query("trial_documents", {"protocol_id": trial_key})
            if trial_docs:
                sections.append("")
                sections.append("Current (non-superseded) documents in this trial:")
                for row in trial_docs:
                    rid = row.get("doc.doc_id", "?")
                    if rid == doc_id:
                        continue  # skip the document being reviewed
                    rtype = row.get("doc.document_type", "?")
                    rver = row.get("doc.version", "—")
                    rfile = row.get("doc.source_file", "?")
                    rcountry = row.get("doc.country", "")
                    rsite = row.get("doc.site_id", "")
                    line = f"  - [{rid}] {rtype} v{rver} ({rfile})"
                    if rcountry:
                        line += f" country={rcountry}"
                    if rsite:
                        line += f" site={rsite}"
                    sections.append(line)
        except RuntimeError:
            pass
    else:
        sections.append("")
        sections.append("## Trial Context")
        sections.append("No trial identifier found — this document is an orphan.")

    return "\n".join(sections)


def _should_skip_review(record: ExtractionRecord) -> bool:
    """Fast-path: skip LLM review for high-confidence, non-ambiguous, non-amendment docs."""
    if detect_amendment_signal(record):
        return False
    if needs_refinement(record):
        return False
    primary = record.classes[0]
    if primary.confidence < 0.95:
        return False
    # Always review CSPs — they could be amendments without explicit "Amendment" in version
    if primary.class_name.value == "CSP":
        return False
    return True


# ---------- Reviewer class ----------

class DocumentReviewer:
    """Iterative reviewer agent.

    Constructed once per pipeline run. Call ``review()`` per document.
    """

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self._agent: Agent[None, ReviewVerdict] = Agent(
            model=model,
            output_type=ReviewVerdict,
            system_prompt=REVIEWER_PROMPT,
        )

    async def review(
        self,
        record: ExtractionRecord,
        client: OmniGraphClient,
        *,
        force: bool = False,
    ) -> ReviewVerdict:
        """Review a document against the current graph state.

        Parameters
        ----------
        force : bool
            If True, skip the fast-path check and always call the LLM.
        """
        if not force and _should_skip_review(record):
            log.debug("  Skipping review for %s (fast-path)", record.filename)
            return ReviewVerdict(
                classification_ok=True,
                amendment=AmendmentDetection(
                    is_amendment=False,
                    reasoning="Skipped — high-confidence, non-amendment document.",
                ),
                reasoning="Fast-path: no review needed.",
            )

        context = _build_review_context(record, client)
        log.info("  Reviewing %s ...", record.filename)
        result = await self._agent.run(context)
        return result.output
