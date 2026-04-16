"""Clinical Picasso — Pass 1 orchestrator.

Preprocessing (load + dedup) -> per-doc LLM extraction (with cache) -> JSON records.

Hardcoded paths for now. Run from the repo root:

    python main.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.extraction import cache
from src.extraction.extract import DEFAULT_MODEL, DocumentExtractor
from src.extraction.schema import ExtractionRecord
from src.preprocessing import DocumentRecord as Doc
from src.preprocessing import Preprocessing
from src.graph.client import OmniGraphClient
from src.ingest.ingestion import ingest
from src.ingest.refinement import refine
from src.cascade.inconsistency_checker import check_all


DATA_DIR = Path("data/")
OUT_DIR = Path("out/records")
GRAPH_DIR = Path("out/graph")
SCHEMA_PATH = Path("schema/clinical.pg")
QUERIES_DIR = Path("queries")
MODEL = DEFAULT_MODEL
CONCURRENCY = 4


async def _extract_or_cache(
    extractor: DocumentExtractor,
    doc: Doc,
    sem: asyncio.Semaphore,
) -> tuple[Doc, ExtractionRecord | Exception, bool]:
    """Return (doc, record-or-error, was_cached)."""
    cached = cache.load(doc.sha256, OUT_DIR)
    if cached is not None:
        return doc, cached, True

    async with sem:
        try:
            record = await extractor.extract(doc)
        except Exception as exc:  # noqa: BLE001 - surface per-doc failure
            return doc, exc, False

    cache.save(record, OUT_DIR)
    return doc, record, False


async def run() -> int:
    pre = Preprocessing('data/').load_all().deduplicate().deduplicate_near().extract_content()
    summary = pre.summary()
    print(
        f"Preprocessing: {summary['total_files']} files, "
        f"{summary['unique']} unique, {summary['duplicates']} duplicates"
    )

    docs = pre.kept
    if not docs:
        print(f"No documents found under {DATA_DIR}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    extractor = DocumentExtractor(model=MODEL)
    sem = asyncio.Semaphore(CONCURRENCY)

    results = await asyncio.gather(
        *(_extract_or_cache(extractor, d, sem) for d in docs)
    )

    extracted = cached = failed = 0
    for doc, outcome, was_cached in results:
        if isinstance(outcome, Exception):
            failed += 1
            print(f"  FAIL   {doc.filename}: {outcome}")
            continue
        primary = outcome.classes[0]
        tag = "CACHED" if was_cached else "EXTRACT"
        if was_cached:
            cached += 1
        else:
            extracted += 1
        print(
            f"  {tag:<7} {doc.filename} -> {primary.class_name.value} "
            f"(conf={primary.confidence:.2f})"
        )

    print(
        f"\nExtraction done: {extracted} extracted, {cached} cached, {failed} failed. "
        f"Records at {OUT_DIR}"
    )

    # Collect successful records for graph ingestion
    records = [outcome for _, outcome, _ in results if not isinstance(outcome, Exception)]
    if not records:
        print("No records to ingest.")
        return 2

    # --- Phase 3-4: Graph init + per-doc ingestion ---
    print(f"\n--- Graph ingestion ({len(records)} records) ---")
    client = OmniGraphClient(GRAPH_DIR, SCHEMA_PATH, QUERIES_DIR)
    client.init(SCHEMA_PATH)

    for rec in records:
        result = ingest(rec, client)
        status = "orphan" if result.is_orphan else f"{len(result.changes)} changes"
        print(f"  INGEST {rec.filename} -> {result.document_type} ({status})")

    # --- Phase 5: Refinement sweep ---
    print("\n--- Refinement ---")
    ref_result = refine(client)
    print(
        f"  {len(ref_result.reclassified)} low-conf, "
        f"{len(ref_result.orphans_connected)} orphans, "
        f"{ref_result.trials_merged} dup trials"
    )

    # --- Phase 6: Audit ---
    print("\n--- Audit ---")
    report = check_all(client)
    print(
        f"  {report.error_count} errors, {report.warning_count} warnings, "
        f"{len(report.issues)} total issues"
    )
    for issue in report.issues:
        print(f"  [{issue.severity}] {issue.category}: {issue.description}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
