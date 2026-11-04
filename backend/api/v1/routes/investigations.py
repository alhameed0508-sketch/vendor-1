"""
Investigation routes — /api/v1/investigations/*

Every read and write goes through the access guard: institution, office and assignment decide
what a caller sees and changes. See access/policy.py.
"""

from access.directory import AccessDirectory
from access.guard import AccessGuard, action_for_transition
from api.deps import get_access_directory, get_audit_service, get_investigation_service
from api.v1.schemas.investigations import (
    AssignRequest,
    InterventionRequest,
    OpenInvestigationRequest,
    TransitionRequest,
)
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from fraud_modules.intervention import request_intervention
from middleware.auth import require_permission
from services.audit_service import AuditService
from services.investigation.investigation_service import InvestigationService
from slowapi import Limiter

router = APIRouter(prefix="/investigations", tags=["investigations"])


def _who(user: dict) -> str:
    return user.get("sub", "investigator")


def get_guard(directory: AccessDirectory = Depends(get_access_directory)) -> AccessGuard:
    return AccessGuard(directory)


def register_investigation_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register investigation routes on the given router."""

    @r.post("")
    @limiter.limit("50/minute")
    def open_investigation(
        request: Request,
        req: OpenInvestigationRequest,
        user: dict = Depends(require_permission("alerts:write")),
        svc: InvestigationService = Depends(get_investigation_service),
        guard: AccessGuard = Depends(get_guard),
    ):
        ctx = guard.opener(user)
        assignee = ctx.user_id if ctx.role == "INVESTIGATOR" else None
        return success_response(
            svc.open(
                req.source,
                req.source_id,
                _who(user),
                institution_id=ctx.institution_id,
                office_id=ctx.office_id,
                assignee=assignee,
            )
        )

    @r.get("")
    @limiter.limit("100/minute")
    def list_investigations(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
        svc: InvestigationService = Depends(get_investigation_service),
        guard: AccessGuard = Depends(get_guard),
    ):
        return success_response({"investigations": guard.visible(user, svc.list_all())})

    @r.get("/{investigation_id}")
    @limiter.limit("100/minute")
    def get_investigation(
        request: Request,
        investigation_id: str,
        user: dict = Depends(require_permission("alerts:read")),
        svc: InvestigationService = Depends(get_investigation_service),
        guard: AccessGuard = Depends(get_guard),
    ):
        investigation = svc.get(investigation_id)
        guard.require(user, "read", investigation)
        return success_response(investigation)

    @r.post("/{investigation_id}/transition")
    @limiter.limit("50/minute")
    def transition_investigation(
        request: Request,
        investigation_id: str,
        req: TransitionRequest,
        user: dict = Depends(require_permission("alerts:write")),
        svc: InvestigationService = Depends(get_investigation_service),
        guard: AccessGuard = Depends(get_guard),
    ):
        guard.require(user, action_for_transition(req.to), svc.get(investigation_id))
        return success_response(
            svc.transition(investigation_id, req.to, _who(user), outcome=req.outcome, note=req.note)
        )

    @r.post("/{investigation_id}/assign")
    @limiter.limit("50/minute")
    def assign_investigation(
        request: Request,
        investigation_id: str,
        req: AssignRequest,
        user: dict = Depends(require_permission("alerts:write")),
        svc: InvestigationService = Depends(get_investigation_service),
        guard: AccessGuard = Depends(get_guard),
    ):
        guard.require(user, "assign", svc.get(investigation_id))
        return success_response(svc.assign(investigation_id, req.assignee, _who(user)))

    @r.post("/{investigation_id}/intervention")
    @limiter.limit("20/minute")
    def investigation_intervention(
        request: Request,
        investigation_id: str,
        req: InterventionRequest,
        user: dict = Depends(require_permission("alerts:write")),
        svc: InvestigationService = Depends(get_investigation_service),
        audit: AuditService = Depends(get_audit_service),
        guard: AccessGuard = Depends(get_guard),
    ):
        investigation = svc.get(investigation_id)
        guard.require(user, "write", investigation)
        return success_response(request_intervention(audit, req.kind, req.account_id, investigation, _who(user)))
