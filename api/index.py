"""Vercel entrypoint: serves the FastAPI app in backend/ as one Python function.

vercel.json rewrites /api/* here; the app sees the original path (/api/v1/...).
The public demo runs in demo mode (synthetic replay), so it must fail closed:
demo mode without auth grants every caller ADMIN, and demo logins fall back to
passwords published in the source unless they are set in the environment.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# backend/ first so its regular `api` package wins over this namespace folder.
sys.path[:0] = [os.path.join(ROOT, "backend"), ROOT]

from core.config import Settings, get_settings  # noqa: E402
from core.production_validator import _DEFAULT_SECRETS  # noqa: E402

DEMO_PASSWORD_VARS = ("DEMO_INVESTIGATOR_PASSWORD", "DEMO_SUPERVISOR_PASSWORD", "DEMO_ADMIN_PASSWORD")
PUBLISHED_DEMO_PASSWORDS = frozenset({"iob@2024", "supervisor@2024", "admin@2024"})
MIN_SECRET_LEN = 32
MIN_DEMO_PASSWORD_LEN = 12


def require_safe_settings(settings: Settings, env=os.environ) -> None:
    if not settings.auth_enabled:
        raise RuntimeError("Refusing to start on Vercel: set AUTH_ENABLED=true")
    if settings.jwt_secret in _DEFAULT_SECRETS or len(settings.jwt_secret) < MIN_SECRET_LEN:
        raise RuntimeError(f"Refusing to start on Vercel: set a strong JWT_SECRET ({MIN_SECRET_LEN}+ characters)")
    for name in DEMO_PASSWORD_VARS:
        value = env.get(name, "")
        if value in PUBLISHED_DEMO_PASSWORDS or len(value) < MIN_DEMO_PASSWORD_LEN:
            raise RuntimeError(f"Refusing to start on Vercel: set {name} ({MIN_DEMO_PASSWORD_LEN}+ characters)")


require_safe_settings(get_settings())

from api.app import app  # noqa: E402,F401
