"""
Audit log routes — /api/v1/audit-log
"""

from typing import Optional

from api.deps import get_audit_service
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from middleware.auth import require_permission, require_role
from services.audit_service import AuditService
from slowapi import Limiter

router = APIRouter(tags=["audit"])


def register_audit_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register audit routes on the given router."""

    @r.get("/audit-log")
    @limiter.limit("100/minute")
    def get_audit_log(
        request: Request,
        alert_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
        user: dict = Depends(require_permission("alerts:read")),
        audit_svc: AuditService = Depends(get_audit_service),
    ):
        """Query the audit trail."""
        return success_response(audit_svc.get_log(alert_id=alert_id, action=action, limit=limit))

    @r.get("/audit-log/integrity")
    @limiter.limit("10/minute")
    def verify_audit_integrity(
        request: Request,
        _user: dict = Depends(require_role("ADMIN", "SUPERVISOR")),
        audit_svc: AuditService = Depends(get_audit_service),
    ):
        """Verify the tamper-evident audit hash chain."""
        return success_response(audit_svc.verify_integrity())
