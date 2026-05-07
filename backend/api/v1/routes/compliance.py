"""
Compliance routes — /api/v1/compliance/*
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from slowapi import Limiter

from core.response import success_response
from middleware.auth import require_permission
from api.deps import get_compliance_service, get_detection_service
from api.v1.schemas.compliance import STRExportRequest
from services.compliance_service import ComplianceService
from services.detection_service import DetectionService

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
