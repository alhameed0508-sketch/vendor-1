"""
Ingest routes — /api/v1/ingest/*
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter

from core.config import get_settings
from core.response import success_response
from api.deps import get_ingest_service, get_detection_service
from services.ingest_service import IngestService
from services.detection_service import DetectionService

router = APIRouter(prefix="/ingest", tags=["ingest"])


def register_ingest_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register ingest routes on the given router."""

    @r.get("/status")
    @limiter.limit("100/minute")
    def ingest_status(
        request: Request,
        ingest_svc: IngestService = Depends(get_ingest_service),
    ):
        """Kafka consumer health and lag metrics."""
        return success_response(ingest_svc.get_status())

    @r.get("/stream-demo")
    @limiter.limit("100/minute")
    def stream_demo(
        request: Request,
        count: int = 10,
        detection_svc: DetectionService = Depends(get_detection_service),
        ingest_svc: IngestService = Depends(get_ingest_service),
    ):
        """Simulated real-time transaction stream for demo visualization."""
        settings = get_settings()
        if not settings.demo_mode:
            raise HTTPException(status_code=404, detail="Not available in production")
        dataset = detection_svc.get_or_generate_dataset()
        return success_response(ingest_svc.get_stream_demo(count, dataset))
