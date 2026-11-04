"""
Graph routes — /api/v1/graph/*
"""

from api.deps import get_detection_service, get_graph_service
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from middleware.auth import require_permission
from services.detection_service import DetectionService
from services.graph_service import GraphService
from slowapi import Limiter

router = APIRouter(prefix="/graph", tags=["graph"])


def register_graph_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register graph routes on the given router."""

    @r.get("/stats")
    @limiter.limit("100/minute")
    def graph_stats(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
        detection_svc: DetectionService = Depends(get_detection_service),
        graph_svc: GraphService = Depends(get_graph_service),
    ):
        dataset = detection_svc.get_or_generate_dataset()
        alerts = detection_svc.ensure_alerts()
        return success_response(graph_svc.get_stats(dataset, alerts))
