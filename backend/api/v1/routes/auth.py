"""
Authentication routes — /api/v1/auth/*
"""

import logging

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter

from core.config import get_settings
from core.exceptions import AuthenticationError
from core.response import success_response
from middleware.auth import get_current_user
from api.deps import get_user_repository, get_redis_client
from api.v1.schemas.auth import LoginRequest, RefreshRequest, LogoutRequest
from repositories.user_repository import UserRepository
from cache.redis_client import RedisClient

from infra.security.auth import (
    authenticate as legacy_authenticate,
    create_access_token,
    create_refresh_token,
    decode_token,
    DEMO_USERS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Redis key prefix for blacklisted refresh tokens
_BLACKLIST_PREFIX = "token:blacklist:"


def register_auth_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register auth routes on the given router."""

    @r.post("/login")
    @limiter.limit("10/minute")
    def login(request: Request, req: LoginRequest):
        """Authenticate and return JWT access + refresh tokens."""
        settings = get_settings()
        client_ip = request.client.host if request.client else "unknown"

        # In demo mode, use legacy authentication (sha256 demo users)
        if settings.demo_mode:
            token = legacy_authenticate(req.username, req.password)
            if not token:
                raise AuthenticationError("Invalid credentials")
            # For demo mode, create a refresh token too
            user = DEMO_USERS.get(req.username, {})
            refresh = create_refresh_token(req.username, user.get("role", "READONLY"))
            return success_response({
                "access_token": token,
                "refresh_token": refresh,
                "token_type": "bearer",
                "auth_enabled": settings.auth_enabled,
            })

        # Production auth flow
        user_repo: UserRepository = get_user_repository()

        # Check account lockout
        if user_repo.check_account_lockout(req.username):
            raise AuthenticationError(
                "Account temporarily locked due to too many failed attempts. "
                "Please try again later."
            )

        # Try LDAP first if enabled
        if settings.ldap_enabled:
            from infra.ldap.ldap_client import authenticate_ldap
            ldap_result = authenticate_ldap(
                username=req.username,
                password=req.password,
                ldap_url=settings.ldap_url,
                bind_dn=settings.ldap_bind_dn,
                bind_password=settings.ldap_bind_password,
                search_base=settings.ldap_search_base,
            )
            if ldap_result:
                # Ensure user exists locally (sync from LDAP)
                local_user = user_repo.find_by_username(req.username)
                if not local_user:
                    user_repo.create_user(
                        username=req.username,
                        password=req.password,
                        role=ldap_result["role"],
                        display_name=ldap_result["display_name"],
                        branch=ldap_result.get("branch", ""),
                    )
                user_repo.record_login_success(req.username)
                access = create_access_token(req.username, ldap_result["role"])
                refresh = create_refresh_token(req.username, ldap_result["role"])
                return success_response({
                    "access_token": access,
                    "refresh_token": refresh,
                    "token_type": "bearer",
                    "auth_enabled": settings.auth_enabled,
                })

        # Local DB authentication
        user = user_repo.find_by_username(req.username)
        if not user:
            user_repo.record_failed_login(req.username, client_ip)
            raise AuthenticationError("Invalid credentials")

        if not user.get("is_active"):
            raise AuthenticationError("Account is deactivated")

        if not user_repo.verify_password(req.password, user["password_hash"]):
            user_repo.record_failed_login(req.username, client_ip)
            raise AuthenticationError("Invalid credentials")

        # Success
        user_repo.record_login_success(req.username)
        access = create_access_token(req.username, user["role"])
        refresh = create_refresh_token(req.username, user["role"])

        return success_response({
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "auth_enabled": settings.auth_enabled,
        })

    @r.post("/refresh")
    @limiter.limit("30/minute")
    def refresh_token(request: Request, req: RefreshRequest):
        """Exchange a valid refresh token for a new access token."""
        payload = decode_token(req.token)
        if not payload:
            raise AuthenticationError("Invalid or expired refresh token")

        if payload.get("type") != "refresh":
            raise AuthenticationError("Token is not a refresh token")

        # Check blacklist
        try:
            redis: RedisClient = get_redis_client()
            if redis.get(f"{_BLACKLIST_PREFIX}{req.token}"):
                raise AuthenticationError("Token has been revoked")
        except AuthenticationError:
            raise
        except Exception as exc:
            logger.warning("Redis blacklist check failed (graceful degradation): %s", exc)

        user_id = payload.get("sub")
        role = payload.get("role", "READONLY")

        new_access = create_access_token(user_id, role)
        return success_response({
            "access_token": new_access,
            "token_type": "bearer",
        })

    @r.post("/logout")
    @limiter.limit("30/minute")
    def logout(request: Request, req: LogoutRequest):
        """Blacklist a refresh token (logout)."""
        payload = decode_token(req.token)
        if payload and payload.get("type") == "refresh":
            try:
                redis: RedisClient = get_redis_client()
                # Blacklist for the remaining TTL of the token
                from datetime import datetime
                exp = payload.get("exp", 0)
                ttl = max(int(exp - datetime.utcnow().timestamp()), 0)
                if ttl > 0:
                    redis.setex(f"{_BLACKLIST_PREFIX}{req.token}", ttl, "1")
            except Exception as exc:
                logger.warning("Redis blacklist write failed (graceful degradation): %s", exc)

        return success_response({"message": "Logged out successfully"})

    @r.get("/me")
    @limiter.limit("100/minute")
    def get_me(request: Request, user: dict = Depends(get_current_user)):
        """Return current user info from JWT."""
        settings = get_settings()
        return success_response({
            "user_id": user.get("sub"),
            "username": user.get("sub"),
            "role": user.get("role"),
            "auth_enabled": settings.auth_enabled,
        })
