"""Per-document extraction: text parse -> LLM call -> DocumentRecord."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pydantic_ai import Agent

from extraction.prompt import EXTRACTION_PROMPT
from extraction.schema import DocumentRecord, LLMExtraction


DEFAULT_MODEL = "anthropic:claude-sonnet-4-5"


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _read_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


_READERS = {
    ".pdf": _read_pdf,
    ".docx": _read_docx,
    ".txt": _read_text,
    ".md": _read_text,
}


def read_document(path: Path) -> str:
    """Dispatch on file extension. Raises on unsupported types."""
    reader = _READERS.get(path.suffix.lower())
    if reader is None:
        raise ValueError(f"Unsupported file type: {path.suffix} ({path})")
    return reader(path)


_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Collapse whitespace. Enough for a stable content hash."""
    return _WS.sub(" ", text).strip()


def content_hash(normalized_text: str) -> str:
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


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

    async def extract(self, path: Path) -> DocumentRecord:
        """Extract a DocumentRecord from a single file (async)."""
        normalized, chash = self._prepare(path)
        result = await self._agent.run(normalized)
        return self._wrap(result.output, path, chash)

    def extract_sync(self, path: Path) -> DocumentRecord:
        """Synchronous variant of `extract`."""
        normalized, chash = self._prepare(path)
        result = self._agent.run_sync(normalized)
        return self._wrap(result.output, path, chash)


    @staticmethod
    def _prepare(path: Path) -> tuple[str, str]:
        text = read_document(path)
        normalized = normalize(text)
        return normalized, content_hash(normalized)

    @staticmethod
    def _wrap(llm_out: LLMExtraction, path: Path, chash: str) -> DocumentRecord:
        return DocumentRecord(
            **llm_out.model_dump(),
            source_file=str(path),
            content_hash=chash,
        )
