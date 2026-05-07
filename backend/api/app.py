"""
MuleCatch Backend API — Application Factory
=============================================
Replaces the monolithic main.py. Creates and configures the FastAPI app
with middleware, error handlers, routers, and startup events.
"""

import os
import sys
import time

os.environ['PYTHONIOENCODING'] = 'utf-8'

# Ensure parent paths are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from core.config import get_settings
from core.error_handlers import register_error_handlers
from core.rate_limiter import create_limiter
from core.response import error_response
from api.v1.router import create_v1_router
from api.v1.routes.health import register_health_routes
from api.deps import get_persistence, get_kafka_consumer
from ingest.kafka_consumer import KAFKA_ENABLED
from api.deps import get_detection_service


def create_app() -> FastAPI:
    """Application factory — builds and configures the FastAPI app."""
    settings = get_settings()

    application = FastAPI(
        title="MuleCatch API",
        description="Mule account detection via explainable graph intelligence",
        version="1.0.0",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    # In production, reject wildcard origins
    cors_origins = settings.cors_origins
    if not settings.demo_mode and "*" in cors_origins:
        cors_origins = [o for o in cors_origins if o != "*"]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Rate Limiter ──────────────────────────────────────────────────────────
    limiter = create_limiter(settings.redis_url)
    application.state.limiter = limiter

    # Custom rate limit exceeded handler (standard envelope)
    @application.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request, exc):
        return error_response(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many requests. Please slow down.",
            status_code=429,
            details=str(exc.detail) if hasattr(exc, 'detail') else None,
        )

    # ── Security Headers ───────────────────────────────────────────────────────
    from middleware.security_headers import SecurityHeadersMiddleware
    application.add_middleware(SecurityHeadersMiddleware)

    # ── Error Handlers ────────────────────────────────────────────────────────
    register_error_handlers(application)

    # ── Prometheus Metrics ────────────────────────────────────────────────────
    try:
        from prometheus_client import (
            Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
        )
        from starlette.responses import Response

        REQUEST_COUNT = Counter(
            "mulecatch_api_requests_total", "Total API requests",
            ["method", "endpoint", "status"],
        )
        REQUEST_DURATION = Histogram(
            "mulecatch_api_request_duration_seconds", "API request duration",
            ["endpoint"],
        )

        @application.middleware("http")
        async def metrics_middleware(request, call_next):
            start = time.time()
            response = await call_next(request)
            duration = time.time() - start
            endpoint = request.url.path
            REQUEST_COUNT.labels(
                method=request.method, endpoint=endpoint, status=response.status_code
            ).inc()
            REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)
            return response

        @application.get("/metrics", tags=["monitoring"])
        def metrics():
            return Response(
                content=generate_latest(), media_type=CONTENT_TYPE_LATEST
            )

    except ImportError:
        pass

    # ── Audit Middleware ──────────────────────────────────────────────────────
    from middleware.auth import audit_middleware
    application.middleware("http")(audit_middleware)

    # ── Routes ────────────────────────────────────────────────────────────────
    # Health routes (no version prefix)
    health_router = __import__("fastapi", fromlist=["APIRouter"]).APIRouter()
    register_health_routes(health_router, limiter)
    application.include_router(health_router)

    # Versioned API routes
    v1_router = create_v1_router(limiter)
    application.include_router(v1_router)

    # ── Startup Events ────────────────────────────────────────────────────────
    @application.on_event("startup")
    async def startup_event():
        """Validate production config and start Kafka consumer if enabled."""
        # Fail fast on insecure production configuration
        if not settings.demo_mode:
            from core.production_validator import validate_or_die
            validate_or_die(settings)

        if KAFKA_ENABLED:
            persistence = get_persistence()
            from api.deps import get_pipeline
            pipeline = get_pipeline()
            consumer = get_kafka_consumer()
            consumer.start(pipeline=pipeline, persistence=persistence)

    return application


# Module-level app instance for uvicorn
app = create_app()
