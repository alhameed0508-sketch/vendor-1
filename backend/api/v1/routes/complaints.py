"""
Fraud complaint routes — /api/v1/complaints/*

Merchants, couriers and telecom partners post evidence to /{id}/evidence; an open case view polls
the case and shows new items as they arrive.
"""

from api.deps import get_complaint_service
from api.v1.schemas.complaints import ComplaintCreateRequest, DecisionRequest, EvidenceRequest
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from middleware.auth import require_permission
from services.complaint_service import ComplaintService
from slowapi import Limiter


def _user(user: dict) -> str:
    return user.get("sub", "desk")


def register_complaint_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register fraud complaint routes on the given router."""

    @r.get("")
    @limiter.limit("100/minute")
    def list_complaints(
        request: Request,
        user: dict = Depends(require_permission("complaints:read")),
        svc: ComplaintService = Depends(get_complaint_service),
    ):
        """Every complaint with its clock, plus the desk's counts."""
        return success_response(svc.list_cases())

    @r.post("")
    @limiter.limit("30/minute")
    def create_complaint(
        request: Request,
        req: ComplaintCreateRequest,
        user: dict = Depends(require_permission("complaints:write")),
        svc: ComplaintService = Depends(get_complaint_service),
    ):
        """Register a customer's fraud complaint and start its clocks."""
        return success_response(svc.create(req.model_dump(mode="json"), _user(user)))

    @r.get("/{complaint_id}")
    @limiter.limit("240/minute")
    def get_complaint(
        request: Request,
        complaint_id: str,
        user: dict = Depends(require_permission("complaints:read")),
        svc: ComplaintService = Depends(get_complaint_service),
    ):
        """One case: evidence, clocks, finding, compensation and the replay of how the finding moved."""
        return success_response(svc.get_case(complaint_id))

    @r.post("/{complaint_id}/evidence")
    @limiter.limit("120/minute")
    def add_evidence(
        request: Request,
        complaint_id: str,
        req: EvidenceRequest,
        user: dict = Depends(require_permission("complaints:write")),
        svc: ComplaintService = Depends(get_complaint_service),
    ):
        """Append one item to the case's hash-chained evidence."""
        return success_response(svc.add_evidence(complaint_id, req.model_dump(mode="json"), _user(user)))

    @r.post("/{complaint_id}/decision")
    @limiter.limit("30/minute")
    def decide(
        request: Request,
        complaint_id: str,
        req: DecisionRequest,
        user: dict = Depends(require_permission("complaints:decide")),
        svc: ComplaintService = Depends(get_complaint_service),
    ):
        """Supervisor records the decision. The recommendation never decides on its own."""
        return success_response(
            svc.decide(complaint_id, req.outcome, req.customer_liability, req.notes, _user(user))
        )

    @r.get("/{complaint_id}/narrative")
    @limiter.limit("30/minute")
    def narrative(
        request: Request,
        complaint_id: str,
        user: dict = Depends(require_permission("complaints:read")),
        svc: ComplaintService = Depends(get_complaint_service),
    ):
        """Plain-English narrative where every sentence cites evidence."""
        return success_response(svc.narrative(complaint_id))

    @r.get("/{complaint_id}/pack")
    @limiter.limit("30/minute")
    def evidence_pack(
        request: Request,
        complaint_id: str,
        user: dict = Depends(require_permission("complaints:export")),
        svc: ComplaintService = Depends(get_complaint_service),
    ):
        """The evidence pack as structured JSON."""
        return success_response(svc.pack(complaint_id, _user(user)))

    @r.get("/{complaint_id}/pack.pdf")
    @limiter.limit("20/minute")
    def evidence_pack_pdf(
        request: Request,
        complaint_id: str,
        user: dict = Depends(require_permission("complaints:export")),
        svc: ComplaintService = Depends(get_complaint_service),
    ):
        """The evidence pack as a PDF."""
        return Response(
            content=svc.pack_pdf(complaint_id, _user(user)),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{complaint_id}_evidence_pack.pdf"'},
        )
