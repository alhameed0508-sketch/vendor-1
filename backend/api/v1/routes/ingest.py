"""
Ingest routes — /api/v1/ingest/*
"""

import json
import logging
import queue

from api.deps import (
    get_dataset_repo,
    get_detection_service,
    get_ingest_service,
)
from core.config import get_settings
from core.response import success_response
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from ingest.kafka_consumer import KAFKA_ENABLED, TransactionConsumer
from middleware.auth import get_current_user, require_permission
from repositories.dataset_repository import DatasetRepository
from services.detection_service import DetectionService
from services.ingest_service import IngestService
from slowapi import Limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


def register_ingest_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register ingest routes on the given router."""

    @r.get("/status")
    @limiter.limit("100/minute")
    def ingest_status(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
        ingest_svc: IngestService = Depends(get_ingest_service),
    ):
        """Kafka consumer health and lag metrics."""
        return success_response(ingest_svc.get_status())

    @r.get("/stream-demo")
    @limiter.limit("100/minute")
    def stream_demo(
        request: Request,
        count: int = 10,
        user: dict = Depends(get_current_user),
        detection_svc: DetectionService = Depends(get_detection_service),
        ingest_svc: IngestService = Depends(get_ingest_service),
    ):
        """Simulated real-time transaction stream for demo visualization."""
        settings = get_settings()
        if not settings.demo_mode:
            raise HTTPException(status_code=404, detail="Not available in production")
        dataset = detection_svc.get_or_generate_dataset()
        return success_response(ingest_svc.get_stream_demo(count, dataset))

    @r.get("/stream")
    async def ingest_stream(
        request: Request,
        user: dict = Depends(get_current_user),
    ):
        """SSE endpoint — pushes new-alert events to connected clients."""
        import asyncio

        async def event_generator():
            while True:
                # Stop streaming when the client disconnects
                if await request.is_disconnected():
                    break
                try:
                    event = TransactionConsumer._alert_event_queue.get_nowait()
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    pass
                # Send keepalive every 2 seconds
                yield ": keepalive\n\n"
                await asyncio.sleep(2)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @r.post("/seed")
    @limiter.limit("10/minute")
    def ingest_seed(
        request: Request,
        num_clusters: int = 3,
        num_legit: int = 20,
        user: dict = Depends(get_current_user),
        detection_svc: DetectionService = Depends(get_detection_service),
        dataset_repo: DatasetRepository = Depends(get_dataset_repo),
    ):
        """Seed synthetic transactions into Kafka for demo/testing."""
        if not KAFKA_ENABLED:
            raise HTTPException(
                status_code=400,
                detail="Kafka is not enabled. Set KAFKA_ENABLED=true.",
            )

        # Ensure dataset (with accounts) is cached so consumer can detect
        detection_svc.get_or_generate_dataset()

        from ingest.kafka_producer import TransactionProducer

        producer = TransactionProducer()
        try:
            count = producer.seed_synthetic(
                num_clusters=num_clusters,
                num_legit=num_legit,
                delay_ms=10,
                dataset_repo=dataset_repo,
            )
        finally:
            producer.close()

        return success_response(
            {
                "seeded": count,
                "topic": producer.topic,
                "message": f"Sent {count} transactions to Kafka",
            }
        )
