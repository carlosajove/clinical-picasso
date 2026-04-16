"""Backfill the `content` field onto existing ExtractionRecord JSONs.

The `content` field was added to ExtractionRecord after some records were
already extracted and cached in `out/records/`. This script walks that
directory, looks up each record's source file in `data/`, populates
`content` using the same logic `Preprocessing.extract_content()` uses at
extraction time, and re-writes the JSON atomically via `cache.save()`.

Records are matched by `raw_sha256` (the JSON filename stem), not by the
`filename` field, so renames in `data/` don't break the mapping.

Usage (from repo root):
    python -m scripts.backfill_content
    python -m scripts.backfill_content --dry-run
    python -m scripts.backfill_content --force
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

from pydantic import ValidationError

from src.extraction import cache
from src.extraction.schema import ExtractionRecord
from src.preprocessing import Preprocessing


DEFAULT_DATA_DIR = Path("data")
DEFAULT_OUT_DIR = Path("out/records")


def build_content_map(data_dir: Path) -> dict[str, str | bytes | None]:
    """Load every file in `data_dir` and return {sha256: content}.

    Uses the canonical Preprocessing pipeline so backfilled content is
    byte-for-byte identical to what a fresh extraction would produce.
    `deduplicate()` is safe (same sha256 → same content); `deduplicate_near()`
    is intentionally skipped because it would drop distinct-sha256 files.
    """
    pre = Preprocessing(data_dir).load_all().deduplicate().extract_content()
    return {doc.sha256: doc.content for doc in pre.kept}


def _describe(content: str | bytes | None) -> str:
    if content is None:
        return "None"
    return f"{type(content).__name__} len={len(content)}"


def backfill(
    data_dir: Path,
    out_dir: Path,
    *,
    force: bool,
    dry_run: bool,
) -> dict[str, int]:
    content_by_sha = build_content_map(data_dir)

    counts = {
        "updated": 0,
        "skipped_existing": 0,
        "missing_source": 0,
        "parse_error": 0,
    }

    for json_path in sorted(out_dir.glob("*.json")):
        try:
            record = ExtractionRecord.model_validate_json(
                json_path.read_text(encoding="utf-8")
            )
        except (ValidationError, ValueError, OSError) as exc:
            print(f"[parse_error] {json_path.name}: {exc}")
            counts["parse_error"] += 1
            continue

        if record.content is not None and not force:
            counts["skipped_existing"] += 1
            continue

        sha = record.raw_sha256
        if sha not in content_by_sha:
            print(f"[missing]     {json_path.name}  (filename={record.filename})")
            counts["missing_source"] += 1
            continue

        raw = content_by_sha[sha]
        # Pydantic's `str | bytes | None` union tries the str branch first
        # during JSON serialization, which raises on non-UTF-8 bytes (e.g. PDFs).
        # Encode bytes as base64 text so model_dump_json() succeeds.
        record.content = base64.b64encode(raw).decode("ascii") if isinstance(raw, bytes) else raw
        tag = "[dry-run]   " if dry_run else "[updated]   "
        print(f"{tag} {json_path.name}  {record.filename}  →  {_describe(record.content)}")

        if not dry_run:
            cache.save(record, out_dir)

        counts["updated"] += 1

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite content even when the record already has a non-null value.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing.",
    )
    args = parser.parse_args()

    if not args.data_dir.is_dir():
        print(f"error: data dir not found: {args.data_dir}", file=sys.stderr)
        return 1
    if not args.out_dir.is_dir():
        print(f"error: out dir not found: {args.out_dir}", file=sys.stderr)
        return 1

    counts = backfill(
        args.data_dir,
        args.out_dir,
        force=args.force,
        dry_run=args.dry_run,
    )

    print()
    print("=" * 60)
    print(f"updated:           {counts['updated']}{'  (dry-run)' if args.dry_run else ''}")
    print(f"skipped (exists):  {counts['skipped_existing']}")
    print(f"missing source:    {counts['missing_source']}")
    print(f"parse errors:      {counts['parse_error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
