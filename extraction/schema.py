"""Pydantic models for Pass 1 document extraction.

The LLM returns an `LLMExtraction`. The pipeline wraps it into a `DocumentRecord`
by adding the non-LLM fields (`source_file`, `content_hash`).
"""

from enum import Enum

from pydantic import BaseModel, Field


class DocumentClass(str, Enum):
    """Closed vocabulary for document classification.

    These are the categories our corpus actually contains. `NOISE` is used for
    documents that are not clinical-trial documents at all (marketing copy,
    unrelated files) — they should be filtered out of the graph downstream.
    """

    CSP = "CSP"                                             # Clinical Study Protocol
    IB = "IB"                                               # Investigator Brochure
    ICF = "ICF"                                             # Informed Consent Form
    CRF = "CRF"                                             # Case Report Form
    CSR = "CSR"                                             # Clinical Study Report
    ETMF = "eTMF"                                           # Generic TMF document
    REGULATORY_GOVERNANCE = "SmPC / DSUR / DSMB Charter"    # Regulatory/governance edge cases
    SYNOPSIS = "Synopsis"
    PATIENT_QUESTIONNAIRE = "Patient Questionnaire"
    INFO_SHEET = "Info Sheet"
    MEDICAL_PUBLICATION = "Medical Publications"
    NOISE = "NOISE"                                         # Not a trial document


class ClassCandidate(BaseModel):
    """One possible classification for the document."""

    class_name: DocumentClass
    """Picked from the closed DocumentClass vocabulary."""

    reasoning: str
    """1-2 sentences citing specific evidence (section titles, signatures, headers)."""

    confidence: float = Field(ge=0, le=1)


class LLMExtraction(BaseModel):
    """Exactly what the LLM is asked to produce."""

    classes: list[ClassCandidate] = Field(min_length=1)

    # Trial identity - registry IDs, one slot per system.
    nct_id: str | None = None
    eudract_id: str | None = None
    eu_ct_id: str | None = None
    isrctn_id: str | None = None
    utn_id: str | None = None
    ind_number: str | None = None
    cta_number: str | None = None

    sponsor_protocol_id: str | None = None
    sponsor_name: str | None = None

    trial_title: str | None = None
    trial_acronym: str | None = None

    # Clinical-trial context - helps relate docs to the right trial.
    intervention: str | None = None
    indication: str | None = None
    therapeutic_area: str | None = None
    phase: str | None = None

    # Content.
    summary: str | None = None

    # Linkage seed - raw citation strings, resolved in Pass 2.
    references_to: list[str] = []


class DocumentRecord(LLMExtraction):
    """Persisted Pass 1 output. Adds pipeline-filled fields to the LLM extraction."""

    source_file: str
    content_hash: str
