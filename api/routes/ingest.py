"""Ingest endpoints — file upload and processing."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse

from api.deps import get_client, refresh_records, DATA_DIR, RECORDS_DIR
from src.extraction.extract import DocumentExtractor
from src.extraction import cache
from src.extraction.schema import ExtractionRecord
from src.graph.serializer import serialize_document, serialize_trial, serialize_belongs_to_trial, _pick_trial_key
from src.ingest.ingestion import ingest
from src.preprocessing import DocumentRecord

log = logging.getLogger(__name__)

router = APIRouter()


async def _process_upload(raw_bytes: bytes, filename: str):
    """Generator that yields SSE events as the pipeline progresses."""

    # Step 1: Preprocessing
    yield _sse("step", {"step": "preprocessing", "status": "running"})
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    doc = DocumentRecord(
        filename=filename,
        size_bytes=len(raw_bytes),
        sha256=sha256,
        raw_bytes=raw_bytes,
    )
    # Extract text content
    from src.preprocessing import Preprocessing
    pre = Preprocessing.__new__(Preprocessing)
    pre.data_dir = DATA_DIR
    pre.documents = [doc]
    pre.kept = [doc]
    pre.removed = []
    pre.extract_content()
    yield _sse("step", {"step": "preprocessing", "status": "done"})

    # Step 2: LLM extraction
    yield _sse("step", {"step": "extraction", "status": "running"})
    cached = cache.load(sha256, RECORDS_DIR)
    if cached is not None:
        record = cached
        yield _sse("step", {"step": "extraction", "status": "done", "cached": True})
    else:
        extractor = DocumentExtractor()
        record = await extractor.extract(doc)
        cache.save(record, RECORDS_DIR)
        yield _sse("step", {"step": "extraction", "status": "done", "cached": False})

    primary = record.classes[0].class_name.value if record.classes else "Unknown"
    confidence = record.classes[0].confidence if record.classes else 0
    yield _sse("classification", {
        "document_type": primary,
        "confidence": confidence,
        "trial": record.sponsor_protocol_id,
        "version": record.version,
    })

    # Step 3: Graph ingestion
    yield _sse("step", {"step": "ingestion", "status": "running"})
    client = get_client()
    try:
        result = await asyncio.to_thread(ingest, record, client)
        yield _sse("step", {"step": "ingestion", "status": "done"})
        yield _sse("result", {
            "doc_id": result.doc_id,
            "document_type": result.document_type,
            "trial_key": result.trial_key,
            "is_orphan": result.is_orphan,
            "changes": [
                {"action": c.action, "target_type": c.target_type, "details": c.details}
                for c in result.changes
            ],
        })
    except Exception as e:
        log.exception("Ingestion failed")
        yield _sse("step", {"step": "ingestion", "status": "error", "error": str(e)})

    # Refresh the in-memory record cache
    refresh_records()

    # Save the raw file to data/ for future reference
    dest = DATA_DIR / filename
    if not dest.exists():
        dest.write_bytes(raw_bytes)

    yield _sse("done", {})


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> StreamingResponse:
    """Upload a document and process it through the pipeline. Returns SSE events."""
    raw_bytes = await file.read()
    filename = file.filename or "upload"

    return StreamingResponse(
        _process_upload(raw_bytes, filename),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
