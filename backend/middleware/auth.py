"""
MuleCatch Authentication Middleware
====================================
Wraps infra.security.auth for FastAPI dependency injection.
Provides Depends-compatible auth guards and rate limiting setup.
"""

import logging
import os
import sys
from typing import Optional
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Ensure infra is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from infra.security.auth import (
    authenticate,
    decode_token,
    has_permission,
    create_token,
    audit_log,
    audit_middleware,
    ROLE_PERMISSIONS,
    DEMO_USERS,
)

from core.config import get_settings
from core.exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)
_demo_warning_shown = False


def _auth_enabled() -> bool:
    return get_settings().auth_enabled


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[dict]:
    """Extract and validate JWT from Authorization header or query parameter.

    Falls back to a ``token`` query parameter so that browser-native
    EventSource (SSE) connections can authenticate — EventSource cannot
    send custom headers.

    When AUTH_ENABLED=false (demo mode), returns a default admin user
    so all endpoints work without authentication.
    """
    settings = get_settings()
    if settings.demo_mode and not settings.auth_enabled:
        global _demo_warning_shown
        if not _demo_warning_shown:
            logger.warning("=" * 60)
            logger.warning("AUTHENTICATION DISABLED — DEMO MODE ACTIVE")
            logger.warning("All requests granted ADMIN access. DO NOT USE IN PRODUCTION.")
            logger.warning("=" * 60)
            _demo_warning_shown = True
        return {"sub": "demo_user", "role": "ADMIN"}

    # Prefer Authorization header; fall back to ?token= query param (SSE)
    raw_token: Optional[str] = None
    if credentials is not None:
        raw_token = credentials.credentials
    else:
        raw_token = request.query_params.get("token")

    if raw_token is None:
        raise AuthenticationError("Missing authentication token")

    payload = decode_token(raw_token)
    if payload is None:
        raise AuthenticationError("Invalid or expired token")

    # Only accept access tokens for API access (not refresh tokens)
    if payload.get("type") == "refresh":
        raise AuthenticationError("Cannot use refresh token for API access")

    return payload


def require_role(*roles: str):
    """FastAPI dependency: require the user to have one of the given roles."""

    async def _guard(user: dict = Depends(get_current_user)):
        if not _auth_enabled():
            return user
        user_role = user.get("role", "")
        if user_role not in roles:
            raise AuthorizationError(
                f"Role '{user_role}' not authorized. Required: {roles}"
            )
        return user

    return _guard


def require_permission(permission: str):
    """FastAPI dependency: require a specific permission string."""

    async def _guard(user: dict = Depends(get_current_user)):
        if not _auth_enabled():
            return user
        user_role = user.get("role", "READONLY")
        allowed = ROLE_PERMISSIONS.get(user_role, [])
        if permission not in allowed:
            raise AuthorizationError(
                f"Permission '{permission}' not granted for role '{user_role}'"
            )
        return user

    return _guard


# Re-export for backwards compat
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")
