"""
Onboarding routes — /api/v1/onboarding/*
Follows the screening.py route registration pattern.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter

from core.response import success_response, error_response
from middleware.auth import require_permission
from api.deps import get_onboarding_service
from services.onboarding_service import OnboardingService
from api.v1.schemas.onboarding import OnboardingAssessRequest, OnboardingBatchRequest


def register_onboarding_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register onboarding risk assessment routes on the given router."""

    @r.post("/onboarding/assess")
    @limiter.limit("100/minute")
    def assess_account(
        request: Request,
        application: OnboardingAssessRequest,
        user: dict = Depends(require_permission("onboarding:write")),
        svc: OnboardingService = Depends(get_onboarding_service),
    ):
        """Assess a single account application for onboarding mule risk."""
        result = svc.assess_account(application.model_dump())
        return success_response(result)

    @r.post("/onboarding/batch")
    @limiter.limit("20/minute")
    def assess_batch(
        request: Request,
        batch: OnboardingBatchRequest,
        user: dict = Depends(require_permission("onboarding:write")),
        svc: OnboardingService = Depends(get_onboarding_service),
    ):
        """Assess multiple account applications in batch."""
        applications = [app.model_dump() for app in batch.applications]
        results = svc.assess_batch(applications)
        return success_response({"results": results, "total": len(results)})

    @r.get("/onboarding/assessments")
    @limiter.limit("100/minute")
    def list_assessments(
        request: Request,
        limit: int = 50,
        offset: int = 0,
        risk_level: Optional[str] = None,
        user: dict = Depends(require_permission("onboarding:read")),
        svc: OnboardingService = Depends(get_onboarding_service),
    ):
        """List onboarding assessments with optional filtering."""
        assessments = svc.get_assessments(
            limit=limit, offset=offset, risk_level=risk_level
        )
        return success_response({
            "assessments": assessments,
            "total": len(assessments),
        })

    @r.get("/onboarding/assessments/{assessment_id}")
    @limiter.limit("100/minute")
    def get_assessment(
        request: Request,
        assessment_id: str,
        user: dict = Depends(require_permission("onboarding:read")),
        svc: OnboardingService = Depends(get_onboarding_service),
    ):
        """Retrieve a single onboarding assessment by ID."""
        result = svc.get_assessment(assessment_id)
        if result is None:
            return error_response(
                code="NOT_FOUND",
                message=f"Assessment {assessment_id} not found",
                status_code=404,
            )
        return success_response(result)

    @r.get("/onboarding/stats")
    @limiter.limit("100/minute")
    def onboarding_stats(
        request: Request,
        user: dict = Depends(require_permission("onboarding:read")),
        svc: OnboardingService = Depends(get_onboarding_service),
    ):
        """Return onboarding risk assessment statistics."""
        return success_response(svc.get_stats())
