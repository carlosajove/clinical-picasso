"""Per-document extraction: preprocessing Doc -> LLM call -> ExtractionRecord."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from pydantic_ai import Agent

from extraction.prompt import EXTRACTION_PROMPT
from extraction.schema import ExtractionRecord, LLMExtraction
# Preprocessing's dataclass is called DocumentRecord; alias as `Doc` locally so
# it reads cleanly next to our Pydantic ExtractionRecord.
from src.preprocessing import DocumentRecord as Doc


DEFAULT_MODEL = "anthropic:claude-sonnet-4-5"


def _read_pdf_bytes(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _read_docx_bytes(data: bytes) -> str:
    from docx import Document

    doc = Document(BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


def _read_text_bytes(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


_READERS = {
    ".pdf": _read_pdf_bytes,
    ".docx": _read_docx_bytes,
    ".txt": _read_text_bytes,
    ".md": _read_text_bytes,
}


def read_doc_bytes(doc: Doc) -> str:
    """Decode a preprocessing Doc's raw bytes to text. Dispatches on filename suffix."""
    suffix = Path(doc.filename).suffix.lower()
    reader = _READERS.get(suffix)
    if reader is None:
        raise ValueError(f"Unsupported file type: {suffix} ({doc.filename})")
    return reader(doc.raw_bytes)


_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Collapse whitespace. Keeps the LLM prompt tight."""
    return _WS.sub(" ", text).strip()


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

    async def extract(self, doc: Doc) -> ExtractionRecord:
        """Extract an ExtractionRecord from a preprocessing Doc (async)."""
        text = self._prepare(doc)
        result = await self._agent.run(text)
        return self._wrap(result.output, doc)

    def extract_sync(self, doc: Doc) -> ExtractionRecord:
        """Synchronous variant of `extract`."""
        text = self._prepare(doc)
        result = self._agent.run_sync(text)
        return self._wrap(result.output, doc)

    # ---- Internals ----

    @staticmethod
    def _prepare(doc: Doc) -> str:
        return normalize(read_doc_bytes(doc))

    @staticmethod
    def _wrap(llm_out: LLMExtraction, doc: Doc) -> ExtractionRecord:
        return ExtractionRecord(
            **llm_out.model_dump(),
            filename=doc.filename,
            raw_sha256=doc.sha256,
        )
