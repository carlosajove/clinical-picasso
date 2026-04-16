"""Clinical Picasso — Full pipeline orchestrator.

Phases 1-2: Preprocessing (load + dedup) -> per-doc LLM extraction (with cache)
Phases 3-4: Graph creation + per-doc ingestion (version resolution, edge discovery, reviewer)
Phase 5:    Refinement sweep
Phase 6:    Audit & inconsistency report

Run from the repo root:

    python main.py                  # Full pipeline (Phases 1-6)
    python main.py --extract-only   # Phases 1-2 only (extraction)
    python main.py --graph-only     # Phases 3-6 only (requires cached records)
    python main.py --no-review      # Skip LLM reviewer in Phase 4
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.extraction import cache
from src.extraction.extract import DEFAULT_MODEL, DocumentExtractor
from src.extraction.schema import ExtractionRecord
from src.graph.client import OmniGraphClient
from src.ingest.ingestion import ingest, IngestResult
from src.ingest.refinement import refine
from src.ingest.reviewer import DocumentReviewer
from src.cascade.inconsistency_checker import check_all
from src.preprocessing import DocumentRecord as Doc
from src.preprocessing import Preprocessing


DATA_DIR = Path("data/")
OUT_DIR = Path("out/records")
GRAPH_DIR = Path("out/graph")
SCHEMA_PATH = Path("schema/clinical.pg")
QUERIES_DIR = Path("queries")
MODEL = DEFAULT_MODEL
CONCURRENCY = 4

log = logging.getLogger(__name__)


# ---------------------------------------------------------------- Phase 1-2

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


async def run_extraction() -> list[ExtractionRecord]:
    """Phases 1-2: Preprocessing + Extraction."""
    pre = Preprocessing('data/').load_all().deduplicate().deduplicate_near().extract_content()
    summary = pre.summary()
    print(
        f"Preprocessing: {summary['total_files']} files, "
        f"{summary['unique']} unique, {summary['duplicates']} duplicates"
    )

    docs = pre.kept
    if not docs:
        print(f"No documents found under {DATA_DIR}")
        return []

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    extractor = DocumentExtractor(model=MODEL)
    sem = asyncio.Semaphore(CONCURRENCY)

    results = await asyncio.gather(
        *(_extract_or_cache(extractor, d, sem) for d in docs)
    )

    records: list[ExtractionRecord] = []
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
        records.append(outcome)

    print(
        f"\nExtraction: {extracted} extracted, {cached} cached, {failed} failed. "
        f"Records at {OUT_DIR}"
    )
    return records


def load_cached_records() -> list[ExtractionRecord]:
    """Load all cached ExtractionRecords from disk."""
    records = []
    for path in sorted(OUT_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            records.append(ExtractionRecord(**data))
        except Exception as e:
            log.warning("Failed to load %s: %s", path, e)
    print(f"Loaded {len(records)} cached records from {OUT_DIR}")
    return records


# ---------------------------------------------------------------- Phase 3-6

async def run_graph_pipeline(
    records: list[ExtractionRecord],
    *,
    use_reviewer: bool = True,
) -> None:
    """Phases 3-6: Graph creation, ingestion, refinement, audit."""

    # Phase 3: Initialize graph
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    client = OmniGraphClient(
        repo_path=GRAPH_DIR,
        schema_path=SCHEMA_PATH,
        queries_dir=QUERIES_DIR,
    )
    client.init(schema_path=SCHEMA_PATH)
    print(f"\nGraph initialized at {GRAPH_DIR}")

    # Phase 4: Per-document ingestion
    reviewer = DocumentReviewer() if use_reviewer else None
    if reviewer:
        print("Reviewer agent enabled")

    amendments = []
    for i, record in enumerate(records, 1):
        result = await ingest(record, client, reviewer=reviewer)
        status = "ORPHAN" if result.is_orphan else "OK"
        print(
            f"  [{i:3d}/{len(records)}] {status:<6} {record.filename} "
            f"-> {result.document_type} (trial={result.trial_key or '—'})"
        )
        if result.amendment_impact:
            amendments.append(result)
            print(
                f"           AMENDMENT: affects {len(result.amendment_impact)} documents"
            )
        if result.review_verdict and not result.review_verdict.classification_ok:
            reclass = result.review_verdict.reclassification
            if reclass:
                print(
                    f"           RECLASSIFIED: {reclass.original_class} -> {reclass.suggested_class}"
                )

    print(f"\nIngestion complete: {len(records)} documents processed")

    # Amendment summary
    if amendments:
        print(f"\n{'='*60}")
        print(f"AMENDMENT IMPACT SUMMARY ({len(amendments)} amendments detected)")
        print(f"{'='*60}")
        for result in amendments:
            print(f"\n  {result.doc_id} ({result.document_type}):")
            if result.review_verdict and result.review_verdict.amendment:
                amend = result.review_verdict.amendment
                print(f"    Label: {amend.amendment_label}")
                print(f"    Scope: {amend.scope}")
            if result.amendment_impact:
                for affected in result.amendment_impact:
                    print(
                        f"    -> {affected.get('document_type', '?')} "
                        f"{affected.get('source_file', '?')} "
                        f"(via {affected.get('cascade_type', '?')})"
                    )

    # Phase 5: Refinement
    print("\nRunning refinement sweep...")
    refinement = refine(client)
    print(
        f"  Reclassified: {len(refinement.reclassified)}, "
        f"Orphans found: {len(refinement.orphans_connected)}, "
        f"New edges: {refinement.new_edges}"
    )

    # Phase 6: Audit
    print("\nRunning audit...")
    report = check_all(client)
    print(f"  Issues: {len(report.issues)} ({report.error_count} errors, {report.warning_count} warnings)")

    # Save audit report
    report_path = GRAPH_DIR / "audit_report.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2))
    print(f"  Report saved to {report_path}")


# ---------------------------------------------------------------- CLI

async def run(args: argparse.Namespace) -> int:
    if args.graph_only:
        records = load_cached_records()
    else:
        records = await run_extraction()

    if not records:
        print("No records to process")
        return 1

    if args.extract_only:
        return 0

    await run_graph_pipeline(records, use_reviewer=not args.no_review)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Clinical Picasso pipeline")
    parser.add_argument("--extract-only", action="store_true", help="Run Phases 1-2 only")
    parser.add_argument("--graph-only", action="store_true", help="Run Phases 3-6 only (use cached records)")
    parser.add_argument("--no-review", action="store_true", help="Skip LLM reviewer in Phase 4")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")

    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
