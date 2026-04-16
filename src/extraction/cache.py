"""Filesystem cache for ExtractionRecords, keyed by raw_sha256.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from src.extraction.schema import ExtractionRecord


def _cache_path(raw_sha256: str, out_dir: Path) -> Path:
    return out_dir / f"{raw_sha256}.json"


def load(raw_sha256: str, out_dir: Path) -> ExtractionRecord | None:
    """Return a cached ExtractionRecord for `raw_sha256`, or None on miss / corrupt JSON."""
    path = _cache_path(raw_sha256, out_dir)
    if not path.exists():
        return None
    try:
        return ExtractionRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, ValueError, OSError) as exc:
        # Corrupt or schema-drifted file -> treat as miss and re-extract.
        print(f"[cache] warning: could not parse {path.name}: {exc}")
        return None


def save(record: ExtractionRecord, out_dir: Path) -> Path:
    """Persist `record` under `out_dir/{raw_sha256}.json`, atomically."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = _cache_path(record.raw_sha256, out_dir)

    # Atomic write: tmp file in same dir + rename.
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(out_dir),
        prefix=f".{record.raw_sha256}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(record.model_dump_json(indent=2, exclude={"content"}))
        tmp_path = Path(tmp.name)

    os.replace(tmp_path, target)
    return target
