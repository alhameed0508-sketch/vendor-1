"""Onboarding mule-risk assessment routes."""

from typing import Optional

from api.deps import get_onboarding_service
from api.v1.schemas.onboarding import (
    EntityResolveRequest,
    OnboardingAssessRequest,
    OnboardingBatchRequest,
)
from core.exceptions import NotFoundError
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from middleware.auth import require_permission
from services.onboarding_service import OnboardingService
from slowapi import Limiter


def register_onboarding_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register onboarding assessment endpoints."""

    @r.post("/resolve-identity")
    @limiter.limit("60/minute")
    def resolve_identity(
        request: Request,
        body: EntityResolveRequest,
        _user: dict = Depends(require_permission("onboarding:write")),
        service: OnboardingService = Depends(get_onboarding_service),
    ):
        return success_response(service.resolve_identity(body.model_dump()))

    @r.post("/assess")
    @limiter.limit("60/minute")
    def assess_account(
        request: Request,
        body: OnboardingAssessRequest,
        _user: dict = Depends(require_permission("onboarding:write")),
        service: OnboardingService = Depends(get_onboarding_service),
    ):
        return success_response(service.assess_account(body.model_dump()))

    @r.post("/assess-batch")
    @limiter.limit("10/minute")
    def assess_batch(
        request: Request,
        body: OnboardingBatchRequest,
        _user: dict = Depends(require_permission("onboarding:write")),
        service: OnboardingService = Depends(get_onboarding_service),
    ):
        applications = [item.model_dump() for item in body.applications]
        return success_response(service.assess_batch(applications))

    @r.get("/assessments")
    @limiter.limit("100/minute")
    def list_assessments(
        request: Request,
        limit: int = 50,
        offset: int = 0,
        risk_level: Optional[str] = None,
        _user: dict = Depends(require_permission("onboarding:read")),
        service: OnboardingService = Depends(get_onboarding_service),
    ):
        safe_limit = min(max(limit, 1), 200)
        safe_offset = max(offset, 0)
        normalized_level = risk_level.upper() if risk_level else None
        return success_response(service.get_assessments(safe_limit, safe_offset, normalized_level))

    @r.get("/assessments/{assessment_id}")
    @limiter.limit("100/minute")
    def get_assessment(
        request: Request,
        assessment_id: str,
        _user: dict = Depends(require_permission("onboarding:read")),
        service: OnboardingService = Depends(get_onboarding_service),
    ):
        assessment = service.get_assessment(assessment_id)
        if assessment is None:
            raise NotFoundError("Onboarding assessment", assessment_id)
        return success_response(assessment)

    @r.get("/stats")
    @limiter.limit("100/minute")
    def get_stats(
        request: Request,
        _user: dict = Depends(require_permission("onboarding:read")),
        service: OnboardingService = Depends(get_onboarding_service),
    ):
        return success_response(service.get_stats())
