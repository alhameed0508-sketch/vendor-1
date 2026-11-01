"""Vercel entrypoint: serves the FastAPI app in backend/ as one Python function.

vercel.json rewrites /api/* here; the app sees the original path (/api/v1/...).
A public URL must fail closed: demo mode without auth grants every caller ADMIN.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# backend/ first so its regular `api` package wins over this namespace folder.
sys.path[:0] = [os.path.join(ROOT, "backend"), ROOT]

from core.config import Settings, get_settings  # noqa: E402


def require_safe_settings(settings: Settings) -> None:
    if not settings.auth_enabled:
        raise RuntimeError("Refusing to start on Vercel: set AUTH_ENABLED=true")
    if settings.jwt_secret == Settings.model_fields["jwt_secret"].default or len(settings.jwt_secret) < 32:
        raise RuntimeError("Refusing to start on Vercel: set a strong JWT_SECRET (32+ characters)")


require_safe_settings(get_settings())

from api.app import app  # noqa: E402,F401
