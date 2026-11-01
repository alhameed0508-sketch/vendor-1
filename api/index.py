"""Vercel entrypoint: serves the FastAPI app in backend/ as one Python function.

vercel.json rewrites /api/* here; the app sees the original path (/api/v1/...).
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# backend/ first so its regular `api` package wins over this namespace folder.
sys.path[:0] = [os.path.join(ROOT, "backend"), ROOT]

from api.app import app  # noqa: E402,F401
