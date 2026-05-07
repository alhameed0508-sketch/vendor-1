"""
Health and root endpoints — no version prefix.
"""

from datetime import datetime

from fastapi import APIRouter, Request
from slowapi import Limiter

from core.response import success_response
from api.deps import get_persistence

router = APIRouter(tags=["health"])


def register_health_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register health routes on the given router."""

    @r.get("/")
    @limiter.limit("100/minute")
    def root(request: Request):
        return success_response({
            "service": "MuleCatch API",
            "version": "1.0.0",
            "status": "operational",
            "docs": "/docs",
        })

    @r.get("/health")
    @limiter.limit("100/minute")
    def health(request: Request):
        persistence = get_persistence()
        return success_response({
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat(),
            "persistence": "neo4j" if persistence.is_persistent else "in-memory",
        })
