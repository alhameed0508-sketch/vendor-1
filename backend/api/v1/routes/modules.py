"""
Module registry and Command Center routes — /api/v1/modules, /api/v1/command-center
"""

from collections import Counter
from typing import Dict

from api.deps import get_alert_service, get_detection_service, get_escalation_service
from core.exceptions import NotFoundError
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from fraud_modules.registry import MODULES, get_module, module_dict
from middleware.auth import require_permission
from services.alert_service import AlertService
from services.detection_service import DetectionService
from services.escalation_service import EscalationService
from slowapi import Limiter

router = APIRouter(tags=["modules"])

ALERT_LIMIT = 100_000
# Only the mule pipeline produces alerts today; other modules report None until they have a findings source.
MODULES_WITH_FINDINGS = {"mule"}


def _alert_summary(alerts: list) -> Dict:
    return {
        "total": len(alerts),
        "by_severity": dict(Counter(a["severity"] for a in alerts)),
        "by_status": dict(Counter(a["status"] for a in alerts)),
    }


def register_module_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register module registry and Command Center routes on the given router."""

    @r.get("/modules")
    @limiter.limit("100/minute")
    def list_modules(request: Request, user: dict = Depends(require_permission("alerts:read"))):
        return success_response({"modules": [module_dict(m) for m in MODULES]})

    @r.get("/modules/{module_id}")
    @limiter.limit("100/minute")
    def get_module_detail(
        request: Request,
        module_id: str,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        try:
            return success_response(module_dict(get_module(module_id)))
        except KeyError:
            raise NotFoundError("Module", module_id) from None

    @r.get("/command-center")
    @limiter.limit("100/minute")
    def command_center(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
        escalation_svc: EscalationService = Depends(get_escalation_service),
    ):
        detection_svc.ensure_alerts()
        alerts = alert_svc.list_alerts(limit=ALERT_LIMIT)["alerts"]
        summary = _alert_summary(alerts)
        modules = [
            {
                **{k: module_dict(m)[k] for k in ("module_id", "name", "status", "workspace_path")},
                "findings": summary["total"] if m.module_id in MODULES_WITH_FINDINGS else None,
            }
            for m in MODULES
        ]
        return success_response(
            {
                "data_source": detection_svc.data_source(),
                "alerts": summary,
                "escalations": {"pending": len(escalation_svc.list_all(status="PENDING"))},
                "modules": modules,
            }
        )
