"""Extraction prompt for Pass 1.

The classification vocabulary is defined once in `extraction.schema.DocumentClass`
(a str Enum). Pydantic AI will enforce it at validation time, but we ALSO
describe each class in the prompt so the LLM picks intelligently.
"""

from src.extraction.schema import DocumentClass


# Human-readable description for each class, shown to the LLM.
_CLASS_DESCRIPTIONS: dict[DocumentClass, str] = {
    DocumentClass.CSP: (
        "Clinical Study Protocol — the full protocol document, the 'bible' of the "
        "trial. Includes the original protocol and any protocol amendments."
    ),
    DocumentClass.IB: (
        "Investigator Brochure — reference document summarizing everything known "
        "about the investigational drug (safety, pharmacology, prior clinical data)."
    ),
    DocumentClass.ICF: (
        "Informed Consent Form — the patient consent record. Includes master ICFs, "
        "country-adapted ICFs, site-adapted ICFs, and signed subject consents."
    ),
    DocumentClass.CRF: (
        "Case Report Form — per-patient, per-visit data capture form (paper or "
        "eCRF screenshots)."
    ),
    DocumentClass.CSR: (
        "Clinical Study Report — the full trial narrative prepared for regulators "
        "at study end."
    ),
    DocumentClass.ETMF: (
        "Electronic Trial Master File document — a regulated TMF document that "
        "does NOT fit a more specific class above. Use this for site files, "
        "regulatory filings, monitoring reports, delegation logs, etc."
    ),
    DocumentClass.REGULATORY_GOVERNANCE: (
        "Regulatory and governance edge cases: SmPC (Summary of Product "
        "Characteristics), DSUR (Development Safety Update Report), or DSMB "
        "(Data Safety Monitoring Board) Charter."
    ),
    DocumentClass.SYNOPSIS: (
        "Synopsis of a Clinical Study Protocol — a short high-level summary of "
        "the protocol, NOT the full protocol."
    ),
    DocumentClass.PATIENT_QUESTIONNAIRE: (
        "Patient-facing questionnaire to collect information about symptoms, "
        "health status, or trial experience (PROs, surveys)."
    ),
    DocumentClass.INFO_SHEET: (
        "Informational sheet describing what a participant should expect during "
        "the trial (not a consent form and not a questionnaire)."
    ),
    DocumentClass.MEDICAL_PUBLICATION: (
        "Published medical literature — research papers, journal articles, "
        "conference abstracts. Related to the trial topic but not a trial "
        "artifact itself."
    ),
    DocumentClass.NOISE: (
        "NOT a trial document. Marketing material, unrelated PDFs, random files, "
        "blank pages, anything that should NOT be part of the TMF."
    ),
}


_CLASS_LIST_BLOCK = "\n".join(
    f"- {c.value!r}: {_CLASS_DESCRIPTIONS[c]}" for c in DocumentClass
)


EXTRACTION_PROMPT: str = f"""\
You are a clinical trial document analyst. Given the full text of a single
document, extract structured metadata matching the schema.

# Classification

Use EXACTLY one of these strings for each candidate's `class_name`:

{_CLASS_LIST_BLOCK}

Rules:
- `classes` must contain at least one entry. Return a SINGLE entry unless the
  document genuinely fits multiple classes with comparable evidence (e.g. a
  bundled PDF that is both a Protocol Amendment and a Safety Update).
- For every candidate, write `reasoning` as 1-2 sentences citing specific
  evidence (section headings, signature blocks, header metadata, explicit
  self-identification). Do NOT write generic reasoning.
- `confidence` in [0, 1] reflects your certainty. The highest-confidence
  candidate is treated as the primary pick downstream.
- If the document clearly isn't a trial document, use `NOISE`.

# Trial identifiers

Extract every identifier that is EXPLICITLY present in the document text.
Never invent IDs. If a field is not stated, leave it null.

- `nct_id`            : ClinicalTrials.gov, format `NCT` + 8 digits
- `eudract_id`        : EU legacy, format `YYYY-NNNNNN-CC`
- `eu_ct_id`          : EU CTIS (new), format `YYYY-NNNNNN-CC`
- `isrctn_id`         : format `ISRCTN` + 8 digits
- `utn_id`            : WHO UTN, format `UNNNN-NNNN-NNNN`
- `ind_number`        : US FDA IND application number
- `cta_number`        : Non-US regulatory authorization number
- `sponsor_protocol_id` : sponsor's internal protocol code (free-form)
- `sponsor_name`      : sponsoring organization

EudraCT vs EU CT disambiguation (same format):
- If the text says "EudraCT" near the ID  ->  `eudract_id`
- If the text says "EU CT Number" or "CTIS"  ->  `eu_ct_id`
- If truly ambiguous and the document is dated before 2023-01-31  ->  prefer
  `eudract_id`; otherwise prefer `eu_ct_id`.

# Clinical context

Extract only what the document states. Do not infer from general knowledge.

- `intervention`      : drug / device / procedure name (brand + code if given)
- `indication`        : specific disease or condition being studied
- `therapeutic_area`  : higher-level area (e.g. "Oncology", "Cardiology")
- `phase`             : one of "1", "1/2", "2", "2/3", "3", "4", "N/A"

# Document versioning and scope

Extract only what the document explicitly states. Do not infer.

- `version`   : document version string exactly as stated, e.g. "1.0", "2.1",
  "Amendment 2", "Edition 3". Null if not stated.
- `country`   : country this document is scoped to, as ISO 3166-1 alpha-2 code
  (e.g. "ES", "DE", "FR", "US"). Null if the document is not
  country-specific or the country is not stated.
- `site_id`   : clinical site or center identifier exactly as stated, e.g.
  "Site 001", "Center 42", "Investigator Site 101". Null if the
  document is not site-specific or the site is not stated.

# Summary

`summary`: 2-3 sentences plainly describing what this document is and its
purpose within the trial. No speculation, no filler. For NOISE documents,
briefly state why it isn't a trial document.

# References

`references_to`: every explicit mention of another document, by title, ID,
version, or section. Keep strings verbatim (e.g. "per Protocol v2.1 §7.2",
"IRB approval letter dated 2024-06-14"). Do not paraphrase.

# Output

Return ONLY the structured output matching the schema. No commentary.
"""


USER_PROMPT_TEMPLATE: str = """\
Extract structured metadata from the clinical-trial document below.

Filename: {filename}

Treat the filename as a weak hint only — every extracted field must be grounded
in the document content itself. Return ONLY the structured output.
"""
