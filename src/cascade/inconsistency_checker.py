"""Graph-wide inconsistency checker.

Run on demand to audit the graph for problems. Works on the latest
(non-superseded) version of every document.

Checks:
  1. Stale parents — a doc derives from a superseded parent when a newer version exists
  2. Stale references — a doc references a superseded document
  3. Stale governance — a governance doc governs a superseded document
  4. Orphan documents — docs with no edges at all
  5. Low-confidence classifications — docs where the classifier was uncertain
  6. Missing expected documents — trial has some doc types but is missing others
  7. Version gaps — v1.0 and v3.0 exist but no v2.0
  8. Metadata conflicts — docs in the same trial with conflicting sponsor/phase
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from src.graph.client import OmniGraphClient

log = logging.getLogger(__name__)

LOW_CONFIDENCE_THRESHOLD = 0.6

# Doc types we expect every trial to have at minimum.
EXPECTED_TYPES = {"CSP", "ICF", "IB"}


@dataclass
class Issue:
    """One inconsistency found in the graph."""
    severity: str           # "error", "warning", "info"
    category: str           # which check found it
    doc_id: str | None      # primary document involved (None for trial-level issues)
    description: str        # human-readable explanation
    details: dict = field(default_factory=dict)


@dataclass
class AuditReport:
    """Full inconsistency report."""
    issues: list[Issue] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def add(self, issue: Issue) -> None:
        self.issues.append(issue)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    def to_dict(self) -> dict:
        by_category: dict[str, list[dict]] = defaultdict(list)
        for issue in self.issues:
            by_category[issue.category].append({
                "severity": issue.severity,
                "doc_id": issue.doc_id,
                "description": issue.description,
                "details": issue.details,
            })
        return {
            "total_issues": len(self.issues),
            "errors": self.error_count,
            "warnings": self.warning_count,
            "by_category": dict(by_category),
        }


def check_all(client: OmniGraphClient) -> AuditReport:
    """Run all inconsistency checks and return a report."""
    report = AuditReport()

    _check_stale_parents(client, report)
    _check_stale_references(client, report)
    _check_stale_governance(client, report)
    _check_orphans(client, report)
    _check_low_confidence(client, report)
    _check_missing_doc_types(client, report)
    _check_version_gaps(client, report)
    _check_metadata_conflicts(client, report)

    log.info(
        "Audit complete: %d issues (%d errors, %d warnings)",
        len(report.issues), report.error_count, report.warning_count,
    )
    return report


def _check_stale_parents(client: OmniGraphClient, report: AuditReport) -> None:
    """Docs that derive from a superseded parent."""
    rows = client.query("stale_parents")
    for row in rows:
        report.add(Issue(
            severity="error",
            category="stale_parent",
            doc_id=row["child.doc_id"],
            description=(
                f"{row['child.document_type']} '{row['child.source_file']}' "
                f"derives from {row['parent.document_type']} v{row.get('parent.version', '?')} "
                f"which has been superseded by v{row.get('newer.version', '?')}"
            ),
            details={
                "child": row["child.doc_id"],
                "stale_parent": row["parent.doc_id"],
                "current_version": row["newer.doc_id"],
            },
        ))


def _check_stale_references(client: OmniGraphClient, report: AuditReport) -> None:
    """Docs that reference a superseded document."""
    rows = client.query("stale_references")
    for row in rows:
        report.add(Issue(
            severity="warning",
            category="stale_reference",
            doc_id=row["doc.doc_id"],
            description=(
                f"{row['doc.document_type']} '{row['doc.source_file']}' "
                f"references {row['ref.document_type']} v{row.get('ref.version', '?')} "
                f"which has been superseded by v{row.get('newer.version', '?')}"
            ),
            details={
                "doc": row["doc.doc_id"],
                "stale_ref": row["ref.doc_id"],
                "current_version": row["newer.doc_id"],
            },
        ))


def _check_stale_governance(client: OmniGraphClient, report: AuditReport) -> None:
    """Governance docs that govern a superseded document."""
    rows = client.query("stale_governance")
    for row in rows:
        report.add(Issue(
            severity="warning",
            category="stale_governance",
            doc_id=row["gov.doc_id"],
            description=(
                f"{row['gov.document_type']} '{row['gov.source_file']}' "
                f"governs {row['doc.document_type']} v{row.get('doc.version', '?')} "
                f"which has been superseded by v{row.get('newer.version', '?')}"
            ),
            details={
                "gov_doc": row["gov.doc_id"],
                "stale_doc": row["doc.doc_id"],
                "current_version": row["newer.doc_id"],
            },
        ))


def _check_orphans(client: OmniGraphClient, report: AuditReport) -> None:
    """Documents with no edges at all."""
    rows = client.query("find_orphans")
    for row in rows:
        report.add(Issue(
            severity="warning",
            category="orphan",
            doc_id=row["doc.doc_id"],
            description=(
                f"{row['doc.document_type']} '{row['doc.source_file']}' "
                f"has no connections to any other document or trial"
            ),
        ))


def _check_low_confidence(client: OmniGraphClient, report: AuditReport) -> None:
    """Documents with uncertain classification."""
    rows = client.query("low_confidence", {"threshold": LOW_CONFIDENCE_THRESHOLD})
    for row in rows:
        report.add(Issue(
            severity="warning",
            category="low_confidence",
            doc_id=row["doc.doc_id"],
            description=(
                f"'{row['doc.source_file']}' classified as {row['doc.document_type']} "
                f"with only {row['doc.classification_confidence']:.0%} confidence"
            ),
            details={"raw_classes": row.get("doc.raw_classes")},
        ))


def _check_missing_doc_types(client: OmniGraphClient, report: AuditReport) -> None:
    """Trials that are missing expected document types."""
    trials = client.query("all_trials")
    for trial_row in trials:
        pid = trial_row["trial.protocol_id"]
        docs = client.query("trial_documents", {"protocol_id": pid})
        types_present = {row.get("doc.document_type") for row in docs}

        for expected in EXPECTED_TYPES:
            if expected not in types_present:
                report.add(Issue(
                    severity="info",
                    category="missing_doc_type",
                    doc_id=None,
                    description=f"Trial {pid} has no {expected} document",
                    details={"trial": pid, "missing_type": expected},
                ))


def _check_version_gaps(client: OmniGraphClient, report: AuditReport) -> None:
    """Version sequences with gaps (e.g., v1.0 and v3.0 but no v2.0)."""
    all_docs = client.query("all_documents")

    # Group by (trial-related fields, document_type)
    groups: dict[tuple, list[str]] = defaultdict(list)
    for row in all_docs:
        doc_type = row.get("doc.document_type", "")
        version = row.get("doc.version")
        if version:
            groups[(doc_type,)].append(version)

    for key, versions in groups.items():
        try:
            nums = sorted(
                [tuple(int(x) for x in v.replace("v", "").split(".")) for v in versions]
            )
        except (ValueError, AttributeError):
            continue

        if len(nums) < 2:
            continue

        # Check for major version gaps
        majors = [n[0] for n in nums]
        for i in range(len(majors) - 1):
            if majors[i + 1] - majors[i] > 1:
                report.add(Issue(
                    severity="info",
                    category="version_gap",
                    doc_id=None,
                    description=(
                        f"{key[0]}: versions jump from "
                        f"{'.'.join(str(x) for x in nums[i])} to "
                        f"{'.'.join(str(x) for x in nums[i+1])}"
                    ),
                ))


def _check_metadata_conflicts(client: OmniGraphClient, report: AuditReport) -> None:
    """Documents in the same trial with conflicting metadata."""
    trials = client.query("all_trials")
    for trial_row in trials:
        pid = trial_row["trial.protocol_id"]
        docs = client.query("trial_documents", {"protocol_id": pid})

        sponsors = set()
        phases = set()
        for row in docs:
            s = row.get("doc.sponsor_name") if "doc.sponsor_name" in row else None
            p = row.get("doc.phase") if "doc.phase" in row else None
            if s:
                sponsors.add(s)
            if p:
                phases.add(p)

        if len(sponsors) > 1:
            report.add(Issue(
                severity="warning",
                category="metadata_conflict",
                doc_id=None,
                description=f"Trial {pid} has documents with different sponsor names: {sponsors}",
                details={"trial": pid, "sponsors": list(sponsors)},
            ))

        if len(phases) > 1:
            report.add(Issue(
                severity="warning",
                category="metadata_conflict",
                doc_id=None,
                description=f"Trial {pid} has documents with different phases: {phases}",
                details={"trial": pid, "phases": list(phases)},
            ))
