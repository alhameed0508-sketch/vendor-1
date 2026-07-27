"""
Feedback routes — /api/v1/feedback/*
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from slowapi import Limiter

from core.response import success_response
from middleware.auth import require_permission, require_role
from api.deps import (
    get_detection_service,
    get_feedback_service,
    get_audit_service,
)
from api.v1.schemas.feedback import FeedbackRequest
from services.detection_service import DetectionService
from services.feedback_service import FeedbackService
from services.audit_service import AuditService

router = APIRouter(prefix="/feedback", tags=["feedback"])


def register_feedback_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register feedback routes on the given router."""

    @r.post("")
    @limiter.limit("30/minute")
    def submit_feedback(
        request: Request,
        req: FeedbackRequest,
        user: dict = Depends(require_permission("feedback:write")),
        detection_svc: DetectionService = Depends(get_detection_service),
        feedback_svc: FeedbackService = Depends(get_feedback_service),
    ):
        """Investigator feedback — feeds active learning loop."""
        detection_svc.ensure_alerts()
        return success_response(
            feedback_svc.submit_feedback(
                alert_id=req.alert_id,
                is_true_positive=req.is_true_positive,
                investigator_id=req.investigator_id,
                notes=req.notes,
                user_id=user.get("sub", "unknown"),
            )
        )

    @r.get("/stats")
    @limiter.limit("100/minute")
    def feedback_stats(
        request: Request,
        user: dict = Depends(require_permission("kpi:read")),
        feedback_svc: FeedbackService = Depends(get_feedback_service),
    ):
        """Feedback statistics for the ROI dashboard."""
        return success_response(feedback_svc.get_stats())

    @r.post("/retrain")
    @limiter.limit("2/minute")
    def trigger_retrain(
        request: Request,
        background_tasks: BackgroundTasks,
        user: dict = Depends(require_role("ADMIN", "SUPERVISOR")),
        feedback_svc: FeedbackService = Depends(get_feedback_service),
        detection_svc: DetectionService = Depends(get_detection_service),
        audit_svc: AuditService = Depends(get_audit_service),
    ):
        """Trigger model retraining based on accumulated feedback."""
        info = feedback_svc.get_retrain_info()
        delta = info["delta"]
        summary = info["summary"]

        background_tasks.add_task(detection_svc.retrain, delta)
        audit_svc.log(
            "RETRAIN_TRIGGERED",
            user.get("sub", "unknown"),
            details=f"delta={delta}, feedback_count={summary['total_feedback']}",
        )

        return success_response(
            {
                "status": "RETRAINING_STARTED",
                "threshold_adjustment": delta,
                "new_smurf_threshold": info["new_threshold"],
                "feedback_count": summary["total_feedback"],
                "false_positive_rate": summary["false_positive_rate"],
                "message": "Pipeline re-running with adjusted thresholds",
            }
        )
