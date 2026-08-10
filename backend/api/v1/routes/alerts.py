"""
Alert routes — /api/v1/alerts/*
"""

from typing import Optional

from api.deps import get_alert_service, get_detection_service
from api.v1.schemas.alerts import AlertUpdateRequest
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from middleware.auth import require_permission
from services.alert_service import AlertService
from services.detection_service import DetectionService
from slowapi import Limiter

router = APIRouter(prefix="/alerts", tags=["alerts"])


def register_alert_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register alert routes on the given router."""

    @r.get("")
    @limiter.limit("100/minute")
    def list_alerts(
        request: Request,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        user: dict = Depends(require_permission("alerts:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
    ):
        detection_svc.ensure_alerts()
        return success_response(alert_svc.list_alerts(severity, status, limit))

    @r.get("/{alert_id}")
    @limiter.limit("100/minute")
    def get_alert(
        request: Request,
        alert_id: str,
        user: dict = Depends(require_permission("alerts:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
    ):
        detection_svc.ensure_alerts()
        return success_response(alert_svc.get_alert(alert_id))

    @r.patch("/{alert_id}")
    @limiter.limit("50/minute")
    def update_alert(
        request: Request,
        alert_id: str,
        req: AlertUpdateRequest,
        user: dict = Depends(require_permission("alerts:write")),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
    ):
        detection_svc.ensure_alerts()
        return success_response(
            alert_svc.update_alert(
                alert_id,
                req.status,
                req.investigator_notes,
                user.get("sub", "unknown"),
            )
        )

    @r.get("/{alert_id}/explanation")
    @limiter.limit("100/minute")
    def get_explanation(
        request: Request,
        alert_id: str,
        user: dict = Depends(require_permission("alerts:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
    ):
        detection_svc.ensure_alerts()
        return success_response(alert_svc.get_explanation(alert_id))

    @r.get("/{alert_id}/narrative")
    @limiter.limit("100/minute")
    def get_narrative(
        request: Request,
        alert_id: str,
        user: dict = Depends(require_permission("alerts:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
    ):
        detection_svc.ensure_alerts()
        return success_response(alert_svc.get_narrative(alert_id))

    @r.get("/{alert_id}/shap")
    @limiter.limit("100/minute")
    def get_shap(
        request: Request,
        alert_id: str,
        user: dict = Depends(require_permission("alerts:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
    ):
        detection_svc.ensure_alerts()
        return success_response(alert_svc.get_shap(alert_id))

    @r.get("/{alert_id}/subgraph")
    @limiter.limit("100/minute")
    def get_subgraph(
        request: Request,
        alert_id: str,
        user: dict = Depends(require_permission("alerts:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
    ):
        detection_svc.ensure_alerts()
        return success_response(alert_svc.get_subgraph(alert_id))
