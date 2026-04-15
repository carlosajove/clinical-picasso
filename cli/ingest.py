"""CLI: ingest a directory of documents and write one DocumentRecord JSON per file.

Usage:
    python -m cli.ingest --input data/sample/ --out out/records/
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from extraction.extract import DEFAULT_MODEL, DocumentExtractor
from extraction.schema import DocumentRecord


SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}


def iter_documents(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {input_dir}")
    return sorted(
        p for p in input_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    )


async def _extract_one(
    extractor: DocumentExtractor, path: Path, out_dir: Path
) -> tuple[Path, DocumentRecord | Exception]:
    try:
        record = await extractor.extract(path)
    except Exception as exc:  # noqa: BLE001 - surface any failure per-file
        return path, exc

    out_path = out_dir / f"{record.content_hash}.json"
    out_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return path, record


async def run(input_dir: Path, out_dir: Path, model: str, concurrency: int) -> int:
    docs = iter_documents(input_dir)
    if not docs:
        print(f"No supported documents found under {input_dir}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {len(docs)} document(s) with model={model} (concurrency={concurrency})")

    extractor = DocumentExtractor(model=model)
    semaphore = asyncio.Semaphore(concurrency)

    async def _gated(path: Path):
        async with semaphore:
            return await _extract_one(extractor, path, out_dir)

    results = await asyncio.gather(*(_gated(p) for p in docs))

    ok = 0
    for path, outcome in results:
        if isinstance(outcome, Exception):
            print(f"  FAIL  {path}: {outcome}", file=sys.stderr)
        else:
            primary = outcome.classes[0]
            print(f"  OK    {path} -> {primary.class_name} (conf={primary.confidence:.2f})")
            ok += 1

    print(f"\nDone: {ok}/{len(docs)} succeeded. Records written to {out_dir}")
    return 0 if ok == len(docs) else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pass 1 ingestion: extract DocumentRecords from a directory.")
    parser.add_argument("--input", type=Path, required=True, help="Directory of source documents")
    parser.add_argument("--out", type=Path, required=True, help="Directory to write DocumentRecord JSON files")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Pydantic AI model id (default: {DEFAULT_MODEL})")
    parser.add_argument("--concurrency", type=int, default=4, help="Max concurrent LLM calls (default: 4)")
    args = parser.parse_args(argv)

    return asyncio.run(run(args.input, args.out, args.model, args.concurrency))


if __name__ == "__main__":
    raise SystemExit(main())
