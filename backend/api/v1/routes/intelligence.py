"""
Cross-module entity intelligence — /api/v1/intelligence/entities/{entity_id}
"""

from api.deps import get_alert_service, get_detection_service
from core.exceptions import NotFoundError
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from fraud_modules.intelligence.collect import collect_findings
from fraud_modules.intelligence.correlate import correlate
from fraud_modules.intelligence.entities import link_accounts
from middleware.auth import require_permission
from services.alert_service import AlertService
from services.detection_service import DetectionService
from slowapi import Limiter

router = APIRouter(tags=["intelligence"])

ALERT_LIMIT = 100_000


def register_intelligence_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register entity intelligence routes on the given router."""

    @r.get("/intelligence/entities/{entity_id}")
    @limiter.limit("100/minute")
    def entity_view(
        request: Request,
        entity_id: str,
        user: dict = Depends(require_permission("alerts:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
    ):
        detection_svc.ensure_alerts()
        dataset = detection_svc.get_or_generate_dataset()
        alerts = alert_svc.list_alerts(limit=ALERT_LIMIT)["alerts"]
        entities = {e.entity.entity_id: e for e in correlate(collect_findings(alerts, dataset))}
        known = entity_id in entities or any(a["account_id"] == entity_id for a in dataset.get("accounts", []))
        if not known:
            raise NotFoundError("Entity", entity_id)

        found = entities.get(entity_id)
        links = [
            {
                "other": vars(link.b if link.a.entity_id == entity_id else link.a),
                "basis": link.basis,
                "confidence": link.confidence,
            }
            for link in link_accounts(dataset.get("accounts", []), dataset.get("transactions", []))
            if entity_id in (link.a.entity_id, link.b.entity_id)
        ]
        modules = [vars(m) for m in found.modules] if found else []
        return success_response(
            {"entity": {"kind": "account", "entity_id": entity_id}, "modules": modules, "links": links}
        )
