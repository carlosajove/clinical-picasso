"""Per-document extraction: preprocessing Doc -> LLM call -> ExtractionRecord."""

from __future__ import annotations

from pydantic_ai import Agent, BinaryContent

from extraction.prompt import EXTRACTION_PROMPT, USER_PROMPT_TEMPLATE
from extraction.schema import ExtractionRecord, LLMExtraction
from src.preprocessing import DocumentRecord


DEFAULT_MODEL = "anthropic:claude-sonnet-4-5"


def _build_query(doc: DocumentRecord) -> list[str | BinaryContent]:
    """Assemble the agent input for one document.

    Preprocessing leaves `doc.content` as:
      - str   for text formats (.txt / .md / .csv / .html),
      - bytes for PDFs and DOCX (DOCX is converted to PDF upstream).

    We always lead with a user prompt (anchors the task and passes the
    filename as a weak hint), then attach the content in the matching
    modality: plain string for text, `BinaryContent` for PDF bytes.
    """
    if doc.content is None:
        raise ValueError(
            f"{doc.filename}: content not populated — "
            "call Preprocessing.extract_content() before extraction"
        )

    user_prompt = USER_PROMPT_TEMPLATE.format(filename=doc.filename)

    if isinstance(doc.content, bytes):
        return [
            user_prompt,
            BinaryContent(data=doc.content, media_type="application/pdf"),
        ]
    return [user_prompt, doc.content]


# ---------- Extractor ----------

class DocumentExtractor:
    """Pass 1 extractor.

    Owns a single Pydantic AI agent configured for the extraction schema.
    Construct once per run (or once per process) and reuse across many documents.
    """

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self._agent: Agent[None, LLMExtraction] = Agent(
            model=model,
            output_type=LLMExtraction,
            system_prompt=EXTRACTION_PROMPT,
        )

    async def extract(self, doc: DocumentRecord) -> ExtractionRecord:
        """Extract an ExtractionRecord from a preprocessing Doc (async)."""
        result = await self._agent.run(_build_query(doc))
        return self._wrap(result.output, doc)

    def extract_sync(self, doc: DocumentRecord) -> ExtractionRecord:
        """Synchronous variant of `extract`."""
        result = self._agent.run_sync(_build_query(doc))
        return self._wrap(result.output, doc)

    # ---- Internals ----

    @staticmethod
    def _wrap(llm_out: LLMExtraction, doc: DocumentRecord) -> ExtractionRecord:
        return ExtractionRecord(
            **llm_out.model_dump(),
            filename=doc.filename,
            raw_sha256=doc.sha256,
        )
