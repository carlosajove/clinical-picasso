from dataclasses import dataclass
from pathlib import Path
import hashlib


@dataclass
class DocumentRecord:
    filename: str
    size_bytes: int
    sha256: str
    raw_bytes: bytes
    is_duplicate: bool = False


class Preprocessing:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.documents: list[DocumentRecord] = []
        self.kept: list[DocumentRecord] = []
        self.removed: list[DocumentRecord] = []

    def load_all(self) -> "Preprocessing":
        """Read every file in data_dir, compute SHA-256 hash."""
        for p in sorted(self.data_dir.iterdir()):
            if p.is_dir() or p.name.startswith("."):
                continue
            raw = p.read_bytes()
            self.documents.append(
                DocumentRecord(
                    filename=p.name,
                    size_bytes=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    raw_bytes=raw,
                )
            )
        return self

    def deduplicate(self) -> "Preprocessing":
        """Group by SHA-256. Keep first occurrence, mark the rest as duplicates."""
        seen: dict[str, DocumentRecord] = {}
        for doc in self.documents:
            if doc.sha256 not in seen:
                seen[doc.sha256] = doc
                self.kept.append(doc)
            else:
                doc.is_duplicate = True
                self.removed.append(doc)
        return self

    def summary(self) -> dict:
        by_ext = {}
        for doc in self.documents:
            ext = Path(doc.filename).suffix.lower()
            by_ext[ext] = by_ext.get(ext, 0) + 1
        return {
            "total_files": len(self.documents),
            "unique": len(self.kept),
            "duplicates": len(self.removed),
            "by_extension": by_ext,
            "duplicates_removed": [d.filename for d in self.removed],
        }
