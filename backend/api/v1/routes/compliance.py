"""
Compliance routes — /api/v1/compliance/*
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from slowapi import Limiter
from typing import Optional

from core.response import success_response, error_response
from middleware.auth import require_permission, require_role
from api.deps import get_compliance_service, get_detection_service, get_str_service
from api.v1.schemas.compliance import STRExportRequest, STRCreateRequest, STRApproveRequest
from services.compliance_service import ComplianceService
from services.detection_service import DetectionService
from services.str_service import STRService

router = APIRouter(prefix="/compliance", tags=["compliance"])


def register_compliance_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register compliance routes on the given router."""

    @r.post("/str-export")
    @limiter.limit("30/minute")
    def export_str(
        request: Request,
        req: STRExportRequest,
        user: dict = Depends(require_permission("str:export")),
        detection_svc: DetectionService = Depends(get_detection_service),
        compliance_svc: ComplianceService = Depends(get_compliance_service),
    ):
        """Generate FIU-compatible STR for selected alerts."""
        alerts = detection_svc.ensure_alerts()
        return success_response(compliance_svc.export_str(req.alert_ids, alerts))

    @r.get("/str-pdf/{alert_id}")
    @limiter.limit("30/minute")
    def export_str_pdf(
        request: Request,
        alert_id: str,
        user: dict = Depends(require_permission("str:export")),
        detection_svc: DetectionService = Depends(get_detection_service),
        compliance_svc: ComplianceService = Depends(get_compliance_service),
    ):
        """Download a single alert's STR as a PDF file."""
        alerts = detection_svc.ensure_alerts()
        pdf_bytes = compliance_svc.generate_pdf(alert_id, alerts)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="STR_{alert_id}.pdf"',
            },
        )

    # ── STR Lifecycle Management ────────────────────────────────────────

    @r.post("/str")
    @limiter.limit("30/minute")
    def create_str(
        request: Request,
        req: STRCreateRequest,
        user: dict = Depends(require_permission("str:export")),
        str_svc: STRService = Depends(get_str_service),
    ):
        """Create a new STR draft."""
        result = str_svc.create_str(
            alert_ids=req.alert_ids,
            account_ids=req.account_ids,
            narrative=req.narrative,
            reporting_entity=req.reporting_entity,
            prepared_by=user.get("sub", "unknown"),
        )
        return success_response(result, status_code=201)

    @r.get("/strs")
    @limiter.limit("100/minute")
    def list_strs(
        request: Request,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        user: dict = Depends(require_permission("str:export")),
        str_svc: STRService = Depends(get_str_service),
    ):
        """List STRs with optional status filter."""
        return success_response(str_svc.list_strs(status=status, limit=limit, offset=offset))

    @r.get("/str/{str_id}")
    @limiter.limit("100/minute")
    def get_str(
        request: Request,
        str_id: str,
        user: dict = Depends(require_permission("str:export")),
        str_svc: STRService = Depends(get_str_service),
    ):
        """Get STR details."""
        result = str_svc.get_str(str_id)
        if result is None:
            return error_response("NOT_FOUND", f"STR {str_id} not found", status_code=404)
        return success_response(result)

    @r.post("/str/{str_id}/approve")
    @limiter.limit("30/minute")
    def approve_str(
        request: Request,
        str_id: str,
        req: STRApproveRequest,
        user: dict = Depends(require_role("ADMIN", "SUPERVISOR")),
        str_svc: STRService = Depends(get_str_service),
    ):
        """Supervisor approval — moves STR from DRAFT to READY_FOR_SUBMISSION."""
        try:
            result = str_svc.approve_for_submission(str_id, approved_by=req.approved_by)
            return success_response(result)
        except ValueError as exc:
            return error_response("INVALID_TRANSITION", str(exc), status_code=400)

    @r.post("/str/{str_id}/submit")
    @limiter.limit("10/minute")
    def submit_str(
        request: Request,
        str_id: str,
        user: dict = Depends(require_role("ADMIN")),
        str_svc: STRService = Depends(get_str_service),
    ):
        """Submit STR to FINGate 2.0 (simulated)."""
        try:
            result = str_svc.submit(str_id)
            return success_response(result)
        except ValueError as exc:
            return error_response("INVALID_TRANSITION", str(exc), status_code=400)

    @r.post("/str/{str_id}/acknowledge")
    @limiter.limit("10/minute")
    def acknowledge_str(
        request: Request,
        str_id: str,
        user: dict = Depends(require_role("ADMIN")),
        str_svc: STRService = Depends(get_str_service),
    ):
        """Mark STR as acknowledged by FIU-IND."""
        try:
            result = str_svc.acknowledge(str_id)
            return success_response(result)
        except ValueError as exc:
            return error_response("INVALID_TRANSITION", str(exc), status_code=400)
