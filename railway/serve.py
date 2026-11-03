"""Railway entrypoint: one service serves the React build and the FastAPI API on one URL.

Demo data lives in memory, so run exactly one replica: a second one would hold
different alerts and investigators would see "Alert not found".

Routing:
  /api/*, /health, /health/detailed, /ready, /docs, /redoc, /openapi.json -> FastAPI
  anything else                                                       -> React build (SPA fallback)
/metrics and /internal/metrics are deliberately not exposed on the public URL.
"""

import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# backend/ first so its regular `api` package wins over the Vercel `api/` folder.
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

from core.config import Settings, get_settings  # noqa: E402
from core.production_validator import _DEFAULT_SECRETS  # noqa: E402
from starlette.responses import FileResponse, PlainTextResponse  # noqa: E402

logger = logging.getLogger("mulecatch.railway")

DEMO_PASSWORD_VARS = ("DEMO_INVESTIGATOR_PASSWORD", "DEMO_SUPERVISOR_PASSWORD", "DEMO_ADMIN_PASSWORD")
PUBLISHED_DEMO_PASSWORDS = frozenset({"iob@2024", "supervisor@2024", "admin@2024"})
MIN_SECRET_LEN = 32
MIN_DEMO_PASSWORD_LEN = 12


def require_safe_settings(settings: Settings, env=os.environ) -> None:
    """Fail closed: a public demo-mode server without auth would grant every caller ADMIN."""
    if not settings.auth_enabled:
        raise RuntimeError("Refusing to start on Railway: set AUTH_ENABLED=true")
    if settings.jwt_secret in _DEFAULT_SECRETS or len(settings.jwt_secret) < MIN_SECRET_LEN:
        raise RuntimeError(f"Refusing to start on Railway: set a strong JWT_SECRET ({MIN_SECRET_LEN}+ characters)")
    for name in DEMO_PASSWORD_VARS:
        value = env.get(name, "")
        if value in PUBLISHED_DEMO_PASSWORDS or len(value) < MIN_DEMO_PASSWORD_LEN:
            raise RuntimeError(f"Refusing to start on Railway: set {name} ({MIN_DEMO_PASSWORD_LEN}+ characters)")


require_safe_settings(get_settings())

from api.app import app as api_app  # noqa: E402

BUILD_DIR = Path(os.getenv("FRONTEND_BUILD_DIR", str(ROOT / "frontend" / "build"))).resolve()
INDEX_HTML = BUILD_DIR / "index.html"
if not INDEX_HTML.is_file():
    logger.warning("Frontend build not found at %s; only the API will be served", BUILD_DIR)

API_EXACT = frozenset({"/api", "/health", "/health/detailed", "/ready", "/docs", "/redoc", "/openapi.json"})
API_PREFIXES = ("/api/", "/docs/")
HIDDEN_PATHS = frozenset({"/metrics", "/internal/metrics"})

SPA_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; connect-src 'self'; "
        "frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
    ),
}
IMMUTABLE = "public, max-age=31536000, immutable"


def is_api_path(path: str) -> bool:
    return path in API_EXACT or path.startswith(API_PREFIXES)


def static_file(path: str):
    """Return the build file for ``path`` if it exists inside the build folder, else None."""
    relative = path.lstrip("/")
    if not relative:
        return None
    candidate = (BUILD_DIR / relative).resolve()
    if BUILD_DIR not in candidate.parents or not candidate.is_file():
        return None
    return candidate


def spa_response(method: str, path: str):
    if method not in ("GET", "HEAD") or path in HIDDEN_PATHS:
        return PlainTextResponse("Not found", status_code=404, headers=SPA_HEADERS)
    if not INDEX_HTML.is_file():
        return PlainTextResponse("Frontend build missing", status_code=503, headers=SPA_HEADERS)
    found = static_file(path)
    if found is not None:
        cache = IMMUTABLE if path.startswith("/static/") else "no-cache"
        return FileResponse(found, headers={**SPA_HEADERS, "Cache-Control": cache})
    # Client-side routes such as /queue or /alert/ALT_123 load the app shell.
    return FileResponse(INDEX_HTML, headers={**SPA_HEADERS, "Cache-Control": "no-cache"})


async def app(scope, receive, send):
    """ASGI dispatcher: API traffic and lifespan go to FastAPI, everything else to the React build."""
    if scope["type"] == "lifespan" or scope["type"] == "websocket":
        await api_app(scope, receive, send)
        return
    path = scope.get("path", "")
    if is_api_path(path):
        await api_app(scope, receive, send)
        return
    response = spa_response(scope.get("method", "GET"), path)
    await response(scope, receive, send)
