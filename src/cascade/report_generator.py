"""Generate audit reports as JSON."""

from __future__ import annotations

import json

from src.cascade.inconsistency_checker import AuditReport


def report_to_json(report: AuditReport, indent: int = 2) -> str:
    """Serialize an AuditReport to a JSON string."""
    return json.dumps(report.to_dict(), indent=indent, ensure_ascii=False)
