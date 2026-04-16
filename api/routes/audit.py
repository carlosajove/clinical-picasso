"""Audit endpoints — inconsistency report."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from api.deps import get_client
from src.cascade.inconsistency_checker import check_all

router = APIRouter()


@router.get("/report")
def audit_report() -> dict:
    """Run all inconsistency checks and return the audit report."""
    client = get_client()
    report = check_all(client)
    return report.to_dict()


@router.get("/report/export")
def audit_report_export() -> JSONResponse:
    """Download the audit report as a JSON file."""
    client = get_client()
    report = check_all(client)
    return JSONResponse(
        content=report.to_dict(),
        headers={"Content-Disposition": "attachment; filename=audit_report.json"},
    )
