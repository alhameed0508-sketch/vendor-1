"""
Security headers middleware — adds HSTS, CSP, X-Content-Type-Options, etc.
"""

from core.config import get_settings
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self' ws: wss:; "
    "frame-ancestors 'self'"
)
# FastAPI's Swagger UI and ReDoc pages load their bundles from jsDelivr (and ReDoc its fonts and a
# web worker), so only those two pages may use those hosts. Every other response keeps CSP above.
DOCS_PATHS = frozenset({"/docs", "/redoc", "/docs/oauth2-redirect"})
DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "img-src 'self' data: blob: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "worker-src 'self' blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        settings = get_settings()

        # Always set these headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"

        response.headers["Content-Security-Policy"] = DOCS_CSP if request.url.path in DOCS_PATHS else CSP

        # HSTS only in production
        if not settings.demo_mode:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
