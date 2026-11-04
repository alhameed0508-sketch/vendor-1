"""
Master v1 router — includes all sub-routers under /api/v1.
"""

from api.v1.routes.alerts import register_alert_routes
from api.v1.routes.audit import register_audit_routes
from api.v1.routes.auth import register_auth_routes
from api.v1.routes.benchmark import register_benchmark_routes
from api.v1.routes.complaints import register_complaint_routes
from api.v1.routes.compliance import register_compliance_routes
from api.v1.routes.csv_upload import register_csv_upload_routes
from api.v1.routes.detection import register_detection_routes
from api.v1.routes.device import register_device_routes
from api.v1.routes.escalations import register_escalation_routes
from api.v1.routes.feedback import register_feedback_routes
from api.v1.routes.genai import register_genai_routes
from api.v1.routes.graph import register_graph_routes
from api.v1.routes.ingest import register_ingest_routes
from api.v1.routes.intelligence import register_intelligence_routes
from api.v1.routes.investigations import register_investigation_routes
from api.v1.routes.kpi import register_kpi_routes
from api.v1.routes.modules import register_module_routes
from api.v1.routes.onboarding import register_onboarding_routes
from api.v1.routes.returns import register_return_routes
from api.v1.routes.roi import register_roi_routes
from api.v1.routes.score import register_score_routes
from api.v1.routes.screening import register_screening_routes
from fastapi import APIRouter
from slowapi import Limiter


def create_v1_router(limiter: Limiter) -> APIRouter:
    """Create and configure the v1 API router with all sub-routes.

    Some route modules use relative paths (e.g., @r.get("") or @r.get("/stats"))
    and expect a prefixed sub-router. Others include their full prefix in the
    decorator path (e.g., @r.get("/kpi")) and can mount on root.
    """
    v1 = APIRouter(prefix="/api/v1")

    # --- Modules that use relative paths — need prefixed sub-routers ---
    auth_router = APIRouter(prefix="/auth", tags=["auth"])
    register_auth_routes(auth_router, limiter)
    v1.include_router(auth_router)

    alerts_router = APIRouter(prefix="/alerts", tags=["alerts"])
    register_alert_routes(alerts_router, limiter)
    v1.include_router(alerts_router)

    feedback_router = APIRouter(prefix="/feedback", tags=["feedback"])
    register_feedback_routes(feedback_router, limiter)
    v1.include_router(feedback_router)

    escalations_router = APIRouter(prefix="/escalations", tags=["escalations"])
    register_escalation_routes(escalations_router, limiter)
    v1.include_router(escalations_router)

    compliance_router = APIRouter(prefix="/compliance", tags=["compliance"])
    register_compliance_routes(compliance_router, limiter)
    v1.include_router(compliance_router)

    complaints_router = APIRouter(prefix="/complaints", tags=["complaints"])
    register_complaint_routes(complaints_router, limiter)
    v1.include_router(complaints_router)

    returns_router = APIRouter(prefix="/returns", tags=["returns"])
    register_return_routes(returns_router, limiter)
    v1.include_router(returns_router)

    graph_router = APIRouter(prefix="/graph", tags=["graph"])
    register_graph_routes(graph_router, limiter)
    v1.include_router(graph_router)

    ingest_router = APIRouter(prefix="/ingest", tags=["ingest"])
    register_ingest_routes(ingest_router, limiter)
    v1.include_router(ingest_router)

    roi_router = APIRouter(prefix="/roi", tags=["roi"])
    register_roi_routes(roi_router, limiter)
    v1.include_router(roi_router)

    csv_upload_router = APIRouter(prefix="/csv-upload", tags=["csv-upload"])
    register_csv_upload_routes(csv_upload_router, limiter)
    v1.include_router(csv_upload_router)

    onboarding_router = APIRouter(prefix="/onboarding", tags=["onboarding"])
    register_onboarding_routes(onboarding_router, limiter)
    v1.include_router(onboarding_router)

    screening_router = APIRouter(prefix="/screening", tags=["screening"])
    register_screening_routes(screening_router, limiter)
    v1.include_router(screening_router)

    score_router = APIRouter(prefix="/score", tags=["score"])
    register_score_routes(score_router, limiter)
    v1.include_router(score_router)

    benchmark_router = APIRouter(prefix="/benchmark", tags=["benchmark"])
    register_benchmark_routes(benchmark_router, limiter)
    v1.include_router(benchmark_router)

    # --- Modules that include full prefix in route paths — mount on v1 ---
    register_detection_routes(v1, limiter)
    register_module_routes(v1, limiter)
    register_intelligence_routes(v1, limiter)
    investigations_router = APIRouter(prefix="/investigations", tags=["investigations"])
    register_investigation_routes(investigations_router, limiter)
    v1.include_router(investigations_router)
    register_kpi_routes(v1, limiter)
    register_audit_routes(v1, limiter)
    register_genai_routes(v1, limiter)
    register_device_routes(v1, limiter)

    return v1
