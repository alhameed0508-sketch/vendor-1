"""
MuleCatch Security Middleware
==============================
Role-based access control, audit logging, and request validation.
Designed for IOB's on-premise security governance requirements.

Roles:
  INVESTIGATOR  - view alerts, update status, export STR
  SUPERVISOR    - all investigator + approve STR batch exports
  ADMIN         - full access including config changes
  READONLY      - view-only access for compliance officers
"""

from fastapi import Request
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import json
import os
from pathlib import Path
import jwt
from jwt import InvalidTokenError
import logging
from logging.handlers import RotatingFileHandler

import bcrypt as _bcrypt

JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE_ME_NOT_FOR_PRODUCTION")
JWT_ALGO = "HS256"
JWT_EXPIRY = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRY_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", "/app/logs/audit.jsonl"))


# Bcrypt password hashing utilities
def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


# ── Rotating audit logger ────────────────────────────────────────────────────
_audit_logger = logging.getLogger("mulecatch.audit")
_audit_logger.setLevel(logging.INFO)
if os.getenv("ENV", "development") == "production":
    # Production audit events go to stdout for collection by the bank's
    # immutable log pipeline/SIEM. Business actions are additionally stored
    # in PostgreSQL's tamper-evident audit chain.
    _audit_handler = logging.StreamHandler()
else:
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _audit_handler = RotatingFileHandler(
            str(AUDIT_LOG_PATH),
            maxBytes=100 * 1024 * 1024,
            backupCount=5,
        )
    except OSError:
        # Read-only test/dev environments still emit audit records.
        _audit_handler = logging.StreamHandler()
_audit_handler.setFormatter(logging.Formatter("%(message)s"))
_audit_logger.addHandler(_audit_handler)

# ── Permissions per role ──────────────────────────────────────────────────────
ROLE_PERMISSIONS: Dict[str, List[str]] = {
    "ADMIN": [
        "alerts:read",
        "alerts:write",
        "alerts:delete",
        "str:export",
        "str:approve",
        "config:read",
        "config:write",
        "feedback:write",
        "kpi:read",
        "screening:read",
        "screening:write",
        "onboarding:read",
        "onboarding:write",
    ],
    "SUPERVISOR": [
        "alerts:read",
        "alerts:write",
        "str:export",
        "str:approve",
        "feedback:write",
        "kpi:read",
        "screening:read",
        "onboarding:read",
        "onboarding:write",
    ],
    "INVESTIGATOR": [
        "alerts:read",
        "alerts:write",
        "str:export",
        "feedback:write",
        "kpi:read",
        "screening:read",
        "onboarding:read",
    ],
    "READONLY": [
        "alerts:read",
        "kpi:read",
        "onboarding:read",
    ],
}

# ── Demo users (only used when ENV != production) ─────────────────────────────
# Passwords sourced from environment variables with dev-only fallbacks.
# In production, ENV=production disables demo mode entirely (see core/config.py).
_DEMO_INVESTIGATOR_PW = os.getenv("DEMO_INVESTIGATOR_PASSWORD", "iob@2024")
_DEMO_SUPERVISOR_PW = os.getenv("DEMO_SUPERVISOR_PASSWORD", "supervisor@2024")
_DEMO_ADMIN_PW = os.getenv("DEMO_ADMIN_PASSWORD", "admin@2024")

DEMO_USERS = {
    "investigator": {
        "password_hash": hash_password(_DEMO_INVESTIGATOR_PW),
        "role": "INVESTIGATOR",
        "display_name": "Fraud Investigator",
        "branch": "Chennai HO",
    },
    "supervisor": {
        "password_hash": hash_password(_DEMO_SUPERVISOR_PW),
        "role": "SUPERVISOR",
        "display_name": "Investigation Supervisor",
        "branch": "Chennai HO",
    },
    "admin": {
        "password_hash": hash_password(_DEMO_ADMIN_PW),
        "role": "ADMIN",
        "display_name": "System Administrator",
        "branch": "HO IT",
    },
}


# ── Token utilities ───────────────────────────────────────────────────────────


def create_token(user_id: str, role: str) -> str:
    """Create an access token (short-lived)."""
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def create_access_token(user_id: str, role: str) -> str:
    """Alias for create_token — explicit access token."""
    return create_token(user_id, role)


def create_refresh_token(user_id: str, role: str) -> str:
    """Create a refresh token (long-lived)."""
    payload = {
        "sub": user_id,
        "role": role,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token: str) -> Optional[Dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except InvalidTokenError:
        return None


def authenticate(username: str, password: str) -> Optional[str]:
    """Authenticate against DEMO_USERS using bcrypt (dev only)."""
    user = DEMO_USERS.get(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return create_token(username, user["role"])


def has_permission(token: str, permission: str) -> bool:
    payload = decode_token(token)
    if not payload:
        return False
    role = payload.get("role", "READONLY")
    return permission in ROLE_PERMISSIONS.get(role, [])


# ── Audit logging ─────────────────────────────────────────────────────────────


def audit_log(
    user_id: str,
    action: str,
    resource: str,
    resource_id: str = "",
    outcome: str = "SUCCESS",
    details: Dict = None,
):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "action": action,
        "resource": resource,
        "resource_id": resource_id,
        "outcome": outcome,
        "details": details or {},
    }
    _audit_logger.info(json.dumps(record))


# ── FastAPI middleware ────────────────────────────────────────────────────────


async def audit_middleware(request: Request, call_next):
    """Logs every API request for RBI audit trail"""
    start = datetime.now(timezone.utc)
    response = await call_next(request)
    elapsed_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000

    # Extract user from token header if present
    auth = request.headers.get("Authorization", "")
    user_id = "anonymous"
    if auth.startswith("Bearer "):
        payload = decode_token(auth[7:])
        if payload:
            user_id = payload.get("sub", "anonymous")

    audit_log(
        user_id=user_id,
        action=f"{request.method} {request.url.path}",
        resource="API",
        outcome="SUCCESS" if response.status_code < 400 else "FAILURE",
        details={
            "status_code": response.status_code,
            "elapsed_ms": round(elapsed_ms, 1),
            "ip": request.client.host if request.client else "unknown",
        },
    )
    return response


# ── Encryption helpers ────────────────────────────────────────────────────────


def mask_account_id(account_id: str) -> str:
    """Masks account ID for non-admin display"""
    if len(account_id) <= 4:
        return "****"
    return account_id[:2] + "*" * (len(account_id) - 4) + account_id[-2:]


def mask_ip(ip: str) -> str:
    """Masks IP for GDPR-style data minimisation"""
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.*.*"
    return "***"
