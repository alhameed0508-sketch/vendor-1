"""
Detection routes — /api/v1/run-detection
"""

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from slowapi import Limiter

from core.response import success_response
from middleware.auth import require_role
from api.deps import get_detection_service
from services.detection_service import DetectionService

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
        """Trigger a fresh detection run on the synthetic dataset."""
        background_tasks.add_task(detection_svc.run_fresh_detection)
        return success_response({
            "message": "Detection pipeline triggered",
        })
