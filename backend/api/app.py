"""
MuleCatch Backend API — Application Factory
=============================================
Replaces the monolithic main.py. Creates and configures the FastAPI app
with middleware, error handlers, routers, and startup events.
"""

import os
import sys
import time
from contextlib import asynccontextmanager

os.environ["PYTHONIOENCODING"] = "utf-8"

# Ensure parent paths are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from core.config import get_settings
from core.error_handlers import register_error_handlers
from core.rate_limiter import create_limiter
from core.response import error_response
from api.v1.router import create_v1_router
from api.v1.routes.health import register_health_routes
from api.deps import get_kafka_consumer
from ingest.kafka_consumer import KAFKA_ENABLED


def create_app() -> FastAPI:
    """Application factory — builds and configures the FastAPI app."""
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """Own startup validation and background-consumer shutdown."""
        if not settings.demo_mode:
            from core.production_validator import validate_or_die

            validate_or_die(settings)

        consumer = None
        if KAFKA_ENABLED:
            from api.deps import get_pipeline, get_alert_repo, get_dataset_repo

            consumer = get_kafka_consumer()
            consumer.start(
                pipeline=get_pipeline(),
                alert_repo=get_alert_repo(),
                dataset_repo=get_dataset_repo(),
            )
        try:
            yield
        finally:
            if consumer is not None:
                consumer.stop()
            from api.deps import close_runtime_resources

            close_runtime_resources()

    application = FastAPI(
        title="MuleCatch API",
        description="Mule account detection via explainable graph intelligence",
        version="1.0.0",
        lifespan=lifespan,
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
            details=str(exc.detail) if hasattr(exc, "detail") else None,
        )

    # ── Security Headers ───────────────────────────────────────────────────────
    from middleware.security_headers import SecurityHeadersMiddleware

    application.add_middleware(SecurityHeadersMiddleware)

    # ── Error Handlers ────────────────────────────────────────────────────────
    register_error_handlers(application)

    # ── Prometheus Metrics ────────────────────────────────────────────────────
    try:
        from prometheus_client import (
            CONTENT_TYPE_LATEST,
            CollectorRegistry,
            Counter,
            Histogram,
            generate_latest,
        )
        from starlette.responses import Response

        metrics_registry = CollectorRegistry(auto_describe=True)
        REQUEST_COUNT = Counter(
            "mulecatch_api_requests_total",
            "Total API requests",
            ["method", "endpoint", "status"],
            registry=metrics_registry,
        )
        REQUEST_DURATION = Histogram(
            "mulecatch_api_request_duration_seconds",
            "API request duration",
            ["endpoint"],
            registry=metrics_registry,
        )

        # Detection-specific metrics
        ALERTS_GENERATED = Counter(
            "mulecatch_alerts_generated_total",
            "Total alerts generated",
            ["severity", "pattern"],
            registry=metrics_registry,
        )
        DETECTION_DURATION = Histogram(
            "mulecatch_detection_duration_seconds",
            "Detection pipeline duration",
            registry=metrics_registry,
        )
        STRS_FILED = Counter(
            "mulecatch_strs_filed_total",
            "Total STRs filed",
            registry=metrics_registry,
        )
        DB_QUERY_DURATION = Histogram(
            "mulecatch_db_query_duration_seconds",
            "Database query duration",
            ["operation"],
            registry=metrics_registry,
        )

        # Store metrics on app state for access from services
        application.state.metrics = {
            "alerts_generated": ALERTS_GENERATED,
            "detection_duration": DETECTION_DURATION,
            "strs_filed": STRS_FILED,
            "db_query_duration": DB_QUERY_DURATION,
        }

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

        from fastapi import Depends as _Depends
        from middleware.auth import require_role as _require_role

        @application.get("/metrics", tags=["monitoring"])
        def metrics(user: dict = _Depends(_require_role("ADMIN"))):
            return Response(
                content=generate_latest(metrics_registry),
                media_type=CONTENT_TYPE_LATEST,
            )

        # Unauthenticated internal metrics endpoint for Prometheus scraping
        # Only accessible within Docker network (not exposed externally)
        @application.get(
            "/internal/metrics", tags=["monitoring"], include_in_schema=False
        )
        def internal_metrics():
            return Response(
                content=generate_latest(metrics_registry),
                media_type=CONTENT_TYPE_LATEST,
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
    return application


# Module-level app instance for uvicorn
app = create_app()
