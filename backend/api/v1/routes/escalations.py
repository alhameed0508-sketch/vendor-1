"""
Escalation routes — /api/v1/escalations/*
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter

from core.response import success_response
from middleware.auth import require_permission, require_role
from api.deps import get_escalation_service
from api.v1.schemas.escalations import EscalationRequest, EscalationActionRequest
from services.escalation_service import EscalationService

router = APIRouter(prefix="/escalations", tags=["escalations"])


def register_escalation_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register escalation routes on the given router."""

    @r.post("")
    @limiter.limit("50/minute")
    def create_escalation(
        request: Request,
        req: EscalationRequest,
        user: dict = Depends(require_permission("alerts:write")),
        esc_svc: EscalationService = Depends(get_escalation_service),
    ):
        """Investigator escalates an alert to supervisor."""
        return success_response(
            esc_svc.create(
                alert_id=req.alert_id,
                reason=req.reason,
                priority=req.priority,
                user_id=user.get("sub", "investigator"),
            )
        )

    @r.get("")
    @limiter.limit("100/minute")
    def list_escalations(
        request: Request,
        status: Optional[str] = None,
        user: dict = Depends(require_permission("alerts:read")),
        esc_svc: EscalationService = Depends(get_escalation_service),
    ):
        """List all escalations, optionally filtered by status."""
        return success_response(esc_svc.list_all(status=status))

    @r.patch("/{escalation_id}")
    @limiter.limit("50/minute")
    def resolve_escalation(
        request: Request,
        escalation_id: str,
        req: EscalationActionRequest,
        user: dict = Depends(require_role("ADMIN", "SUPERVISOR")),
        esc_svc: EscalationService = Depends(get_escalation_service),
    ):
        """Supervisor acts on an escalation: APPROVE, REJECT, or REASSIGN."""
        return success_response(
            esc_svc.resolve(
                escalation_id=escalation_id,
                action=req.action,
                notes=req.notes,
                user_id=user.get("sub", "supervisor"),
            )
        )
