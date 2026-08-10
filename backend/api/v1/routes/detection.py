"""
Detection routes — /api/v1/run-detection
"""

from api.deps import get_detection_service
from core.config import get_settings
from core.exceptions import ConflictError
from core.response import success_response
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from middleware.auth import require_role
from services.detection_service import DetectionService
from slowapi import Limiter

router = APIRouter(tags=["detection"])


def register_detection_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register detection routes on the given router."""

    @r.post("/run-detection")
    @limiter.limit("5/minute")
    def run_detection(
        request: Request,
        background_tasks: BackgroundTasks,
        user: dict = Depends(require_role("ADMIN", "SUPERVISOR")),
        detection_svc: DetectionService = Depends(get_detection_service),
    ):
        """Trigger a fresh synthetic detection run in demonstration mode."""
        if not get_settings().demo_mode:
            raise ConflictError(
                "Synthetic detection runs are disabled in production",
                "Production detection is driven by validated ingest sources.",
            )
        background_tasks.add_task(detection_svc.run_fresh_detection)
        return success_response(
            {
                "message": "Detection pipeline triggered",
            }
        )
