"""
Master v1 router — includes all sub-routers under /api/v1.
"""

from fastapi import APIRouter
from slowapi import Limiter

from api.v1.routes.auth import register_auth_routes
from api.v1.routes.alerts import register_alert_routes
from api.v1.routes.feedback import register_feedback_routes
from api.v1.routes.escalations import register_escalation_routes
from api.v1.routes.compliance import register_compliance_routes
from api.v1.routes.detection import register_detection_routes
from api.v1.routes.ingest import register_ingest_routes
from api.v1.routes.graph import register_graph_routes
from api.v1.routes.kpi import register_kpi_routes
from api.v1.routes.audit import register_audit_routes
from api.v1.routes.screening import register_screening_routes


def create_v1_router(limiter: Limiter) -> APIRouter:
    """Create and configure the v1 API router with all sub-routes."""
    v1 = APIRouter(prefix="/api/v1")

    register_auth_routes(v1, limiter)
    register_alert_routes(v1, limiter)
    register_feedback_routes(v1, limiter)
    register_escalation_routes(v1, limiter)
    register_compliance_routes(v1, limiter)
    register_detection_routes(v1, limiter)
    register_ingest_routes(v1, limiter)
    register_graph_routes(v1, limiter)
    register_kpi_routes(v1, limiter)
    register_audit_routes(v1, limiter)
    register_screening_routes(v1, limiter)

    return v1
