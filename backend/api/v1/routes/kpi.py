"""
KPI routes — /api/v1/kpi
"""

from api.deps import get_detection_service, get_kpi_service
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from middleware.auth import require_permission
from services.detection_service import DetectionService
from services.kpi_service import KPIService
from slowapi import Limiter

router = APIRouter(tags=["kpi"])


def register_kpi_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register KPI routes on the given router."""

    @r.get("/kpi")
    @limiter.limit("100/minute")
    def get_kpi(
        request: Request,
        user: dict = Depends(require_permission("kpi:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        kpi_svc: KPIService = Depends(get_kpi_service),
    ):
        detection_svc.ensure_alerts()
        return success_response(kpi_svc.get_kpis())
