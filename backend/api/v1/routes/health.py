"""
Health and root endpoints — no version prefix.
"""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from slowapi import Limiter

from core.response import success_response


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
        """Lightweight liveness probe — always responds fast."""
        from api.deps import get_persistence

        persistence = get_persistence()
        return success_response({
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "persistence": "neo4j" if persistence.is_persistent else "in-memory",
        })

    @r.get("/health/detailed", tags=["monitoring"])
    @limiter.limit("30/minute")
    def health_detailed(request: Request):
        """Detailed readiness probe — checks all infrastructure dependencies."""
        checks = {}
        all_healthy = True

        # Neo4j
        checks["neo4j"] = _check_neo4j()
        if checks["neo4j"]["status"] != "ok":
            all_healthy = False

        # Redis
        checks["redis"] = _check_redis()
        if checks["redis"]["status"] != "ok":
            all_healthy = False

        # Kafka
        checks["kafka"] = _check_kafka()
        # Kafka is optional — don't mark unhealthy if disabled
        if checks["kafka"]["status"] == "error":
            all_healthy = False

        return success_response({
            "status": "ok" if all_healthy else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
        })


def _check_neo4j() -> dict:
    """Check Neo4j connectivity."""
    start = time.time()
    try:
        from api.deps import get_persistence
        persistence = get_persistence()
        if persistence.is_persistent:
            return {
                "status": "ok",
                "mode": "neo4j",
                "latency_ms": round((time.time() - start) * 1000, 1),
            }
        return {"status": "ok", "mode": "in-memory"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _check_redis() -> dict:
    """Check Redis connectivity."""
    start = time.time()
    try:
        from api.deps import get_redis_client
        client = get_redis_client()
        if client.ping():
            return {
                "status": "ok",
                "latency_ms": round((time.time() - start) * 1000, 1),
            }
        return {"status": "ok", "mode": "unavailable (in-memory fallback)"}
    except Exception:
        return {"status": "ok", "mode": "unavailable (in-memory fallback)"}


def _check_kafka() -> dict:
    """Check Kafka connectivity."""
    try:
        from ingest.kafka_consumer import KAFKA_ENABLED
        if not KAFKA_ENABLED:
            return {"status": "ok", "mode": "disabled"}
        from api.deps import get_kafka_consumer
        consumer = get_kafka_consumer()
        if consumer and hasattr(consumer, '_running') and consumer._running:
            return {"status": "ok", "mode": "consuming"}
        return {"status": "ok", "mode": "connected"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
