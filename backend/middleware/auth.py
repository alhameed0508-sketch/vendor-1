"""
MuleCatch Authentication Middleware
====================================
Wraps infra.security.auth for FastAPI dependency injection.
Provides Depends-compatible auth guards and rate limiting setup.
"""

import os
import sys
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
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

# Auth is optional — controlled by AUTH_ENABLED env var
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[dict]:
    """Extract and validate JWT from Authorization header.

    When AUTH_ENABLED=false, returns a default investigator user
    so all endpoints work in demo mode.
    """
    if not AUTH_ENABLED:
        return {"sub": "demo_user", "role": "ADMIN"}

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def require_role(*roles: str):
    """FastAPI dependency: require the user to have one of the given roles."""

    async def _guard(user: dict = Depends(get_current_user)):
        if not AUTH_ENABLED:
            return user
        user_role = user.get("role", "")
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' not authorized. Required: {roles}",
            )
        return user

    return _guard


def require_permission(permission: str):
    """FastAPI dependency: require a specific permission string."""

    async def _guard(user: dict = Depends(get_current_user)):
        if not AUTH_ENABLED:
            return user
        user_role = user.get("role", "READONLY")
        allowed = ROLE_PERMISSIONS.get(user_role, [])
        if permission not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' not granted for role '{user_role}'",
            )
        return user

    return _guard
