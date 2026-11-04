"""
Return-claim routes — /api/v1/returns/*

Retailers file return claims; six signals are fused into a recommendation a person reviews. Carrier and
bank systems report back through signed webhooks.
"""

import json

from api.deps import get_return_claim_service
from api.v1.schemas.returns import CarrierEvent, ChargebackEvent, ReturnClaimRequest, ReviewRequest
from core.config import get_settings
from core.exceptions import ValidationError
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from middleware.auth import require_permission
from pydantic import ValidationError as PydanticValidationError
from services.return_claim_service import ReturnClaimService
from slowapi import Limiter

SIGNATURE_HEADER = "X-MuleCatch-Signature"


def _user(user: dict) -> str:
    return user.get("sub", "desk")


async def _signed_body(request: Request, svc: ReturnClaimService, model):
    body = await request.body()
    svc.check_signature(body, request.headers.get(SIGNATURE_HEADER), strict=not get_settings().demo_mode)
    try:
        return model.model_validate(json.loads(body))
    except (ValueError, PydanticValidationError) as exc:
        raise ValidationError("Webhook body is not valid", str(exc)[:300]) from exc


def register_return_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register return-claim routes on the given router."""

    @r.get("")
    @limiter.limit("100/minute")
    def list_claims(
        request: Request,
        user: dict = Depends(require_permission("returns:read")),
        svc: ReturnClaimService = Depends(get_return_claim_service),
    ):
        """Every claim with its tier and score, highest first, plus the desk's counts."""
        return success_response(svc.list_claims())

    @r.get("/overview")
    @limiter.limit("100/minute")
    def overview(
        request: Request,
        user: dict = Depends(require_permission("returns:read")),
        svc: ReturnClaimService = Depends(get_return_claim_service),
    ):
        """Where claims stand, the demo scenarios, detected rings, and how far each check reaches."""
        return success_response(svc.overview())

    @r.post("")
    @limiter.limit("30/minute")
    def create_claim(
        request: Request,
        req: ReturnClaimRequest,
        user: dict = Depends(require_permission("returns:write")),
        svc: ReturnClaimService = Depends(get_return_claim_service),
    ):
        """File a return claim, with an optional photo and receipt, and score it."""
        return success_response(svc.create(req, _user(user)))

    @r.get("/{claim_id}")
    @limiter.limit("240/minute")
    def get_claim(
        request: Request,
        claim_id: str,
        user: dict = Depends(require_permission("returns:read")),
        svc: ReturnClaimService = Depends(get_return_claim_service),
    ):
        """One claim: the six signals, the fused tier, and any review."""
        return success_response(svc.get_claim(claim_id))

    @r.post("/{claim_id}/review")
    @limiter.limit("30/minute")
    def review_claim(
        request: Request,
        claim_id: str,
        req: ReviewRequest,
        user: dict = Depends(require_permission("returns:decide")),
        svc: ReturnClaimService = Depends(get_return_claim_service),
    ):
        """A person records the outcome. The recommendation never decides on its own."""
        return success_response(svc.review(claim_id, req.outcome, req.notes, _user(user)))

    @r.get("/{claim_id}/package")
    @limiter.limit("30/minute")
    def package(
        request: Request,
        claim_id: str,
        user: dict = Depends(require_permission("returns:export")),
        svc: ReturnClaimService = Depends(get_return_claim_service),
    ):
        """The bank package as structured JSON, with its integrity hash."""
        return success_response(svc.package(claim_id, _user(user)))

    @r.get("/{claim_id}/package.pdf")
    @limiter.limit("20/minute")
    def package_pdf(
        request: Request,
        claim_id: str,
        user: dict = Depends(require_permission("returns:export")),
        svc: ReturnClaimService = Depends(get_return_claim_service),
    ):
        """The bank package as a PDF."""
        return Response(
            content=svc.package_pdf(claim_id, _user(user)),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{claim_id}_bank_package.pdf"'},
        )

    @r.post("/webhooks/carrier")
    @limiter.limit("300/minute")
    async def carrier_webhook(request: Request, svc: ReturnClaimService = Depends(get_return_claim_service)):
        """Carrier status changes. A lost or damaged parcel eases the claim's score."""
        return success_response(svc.carrier_event(await _signed_body(request, svc, CarrierEvent)))

    @r.post("/webhooks/chargeback")
    @limiter.limit("300/minute")
    async def chargeback_webhook(request: Request, svc: ReturnClaimService = Depends(get_return_claim_service)):
        """Bank chargeback status changes, kept on the claim for the record."""
        return success_response(svc.chargeback_event(await _signed_body(request, svc, ChargebackEvent)))
