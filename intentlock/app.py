"""IntentLock application factory. One process: the API, plus the React build when it is present."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.engine import Engine

from intentlock.ai.llm import LLM, AIUnavailable, build_llm
from intentlock.api.routes import ApiError, Container, build_router, health_payload
from intentlock.db import session as dbs
from intentlock.money import MoneyError
from intentlock.payments.base import PaymentProvider
from intentlock.payments.paypal import PayPalProvider
from intentlock.services import catalog
from intentlock.services.checkout import CheckoutError
from intentlock.services.mandates import MandateError
from intentlock.services.webhooks import WebhookError
from intentlock.settings import Settings, get_settings

logger = logging.getLogger("intentlock")
_UNSET = object()
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


def _fail(status: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"success": False, "data": None, "error": {"code": code, "message": message, "details": details}})


def create_app(settings: Settings | None = None, *, provider: PaymentProvider | None = None, llm: LLM | None | object = _UNSET,
               engine: Engine | None = None, migrate: bool = True) -> FastAPI:  # fmt: skip
    settings = settings or get_settings()
    if provider is None:
        settings.require_valid()
        provider = PayPalProvider(settings.resolved_paypal_base_url, settings.paypal_client_id, settings.paypal_client_secret)
    engine = engine or dbs.make_engine(settings.resolved_database_url)
    if migrate:
        dbs.run_migrations(settings.resolved_database_url)
    else:
        dbs.create_schema_for_tests(engine)
    sessions = dbs.make_session_factory(engine)
    dbs.seed_default_tenant(sessions)
    with sessions() as s:
        catalog.sync_products(s, catalog.DemoCatalogProvider())

    app = FastAPI(title="Netrava IntentLock API", version="0.1.0", description="Purchase intent integrity for AI commerce")
    app.state.container = Container(settings=settings, sessions=sessions, provider=provider, llm=build_llm(settings) if llm is _UNSET else llm)
    if settings.database_kind != "postgresql":
        logger.warning("IntentLock is using SQLite. Data is not durable; set DATABASE_URL to PostgreSQL for a deployment.")

    app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_url], allow_credentials=True, allow_methods=["GET", "POST", "PUT"],
                       allow_headers=["content-type", "x-intentlock-client"])  # fmt: skip

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    # ── errors: one envelope, no stack traces ────────────────────────────────
    for exc_type in (ApiError, MandateError, CheckoutError, WebhookError):

        @app.exception_handler(exc_type)
        async def _domain(_request: Request, exc):  # noqa: ANN001
            return _fail(exc.status, exc.code, exc.message, getattr(exc, "details", None))

    @app.exception_handler(AIUnavailable)
    async def _ai(_request: Request, exc: AIUnavailable):
        return _fail(503, "AI_UNAVAILABLE", str(exc))

    @app.exception_handler(MoneyError)
    async def _money(_request: Request, exc: MoneyError):
        return _fail(422, "INVALID_AMOUNT", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return _fail(422, "VALIDATION_ERROR", "Some fields are missing or invalid", details)

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, exc: Exception):
        logger.exception("Unhandled error: %s", type(exc).__name__)
        return _fail(500, "INTERNAL_ERROR", "Something went wrong. Nothing was captured by this request.")

    @app.get("/health")
    def health():
        return health_payload(app.state.container)

    app.include_router(build_router())

    # ── React build (same origin, so the session cookie is first-party) ──────
    build_dir = Path(settings.frontend_build_dir).resolve()
    index = build_dir / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return _fail(404, "NOT_FOUND", "Not found")
        if not index.is_file():
            return _fail(404, "FRONTEND_NOT_BUILT", "The web app has not been built; the API is available under /api/v1")
        candidate = (build_dir / path).resolve()
        if path and build_dir in candidate.parents and candidate.is_file():
            cache = "public, max-age=31536000, immutable" if path.startswith("static/") else "no-cache"
            return FileResponse(candidate, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return app
