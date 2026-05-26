"""
GenAI routes — /api/v1/genai/*
LLM-powered forensic analysis, investigation chat, and onboarding explanation.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from slowapi import Limiter

from core.response import success_response, error_response
from middleware.auth import get_current_user, require_permission
from api.deps import (
    get_genai_service,
    get_alert_service,
    get_detection_service,
    get_onboarding_service,
)
from services.genai_service import GenAIService
from services.alert_service import AlertService
from services.detection_service import DetectionService
from services.onboarding_service import OnboardingService


class ChatRequest(BaseModel):
    message: str
    alert_id: Optional[str] = None
    conversation_history: Optional[List[dict]] = None


class TriageRequest(BaseModel):
    alert_data: dict = Field(..., description="Alert data for triage analysis")


class PatternDiscoveryRequest(BaseModel):
    num_clusters: int = Field(3, ge=1, le=50)
    num_legit: int = Field(30, ge=1, le=500)


class OnboardingExplainRequest(BaseModel):
    assessment_id: Optional[str] = None
    assessment_data: Optional[dict] = None


def register_genai_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register GenAI routes on the given router."""

    @r.get("/genai/status")
    @limiter.limit("100/minute")
    def genai_status(
        request: Request,
        user: dict = Depends(get_current_user),
        svc: GenAIService = Depends(get_genai_service),
    ):
        """Return current GenAI status — enabled, provider, fallback state."""
        return success_response(svc.get_status())

    @r.post("/genai/analyze/{alert_id}")
    @limiter.limit("30/minute")
    def analyze_alert(
        request: Request,
        alert_id: str,
        user: dict = Depends(require_permission("alerts:read")),
        genai_svc: GenAIService = Depends(get_genai_service),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
    ):
        """Generate LLM forensic analysis for an alert."""
        detection_svc.ensure_alerts()
        alert_data = alert_svc.get_alert(alert_id)
        if alert_data is None:
            return error_response(
                code="NOT_FOUND",
                message=f"Alert {alert_id} not found",
                status_code=404,
            )
        analysis = genai_svc.analyze_alert(alert_data)
        return success_response(analysis.to_dict())

    @r.post("/genai/chat")
    @limiter.limit("60/minute")
    def investigation_chat(
        request: Request,
        body: ChatRequest,
        user: dict = Depends(require_permission("alerts:read")),
        genai_svc: GenAIService = Depends(get_genai_service),
        detection_svc: DetectionService = Depends(get_detection_service),
        alert_svc: AlertService = Depends(get_alert_service),
    ):
        """Investigation assistant — conversational Q&A about alerts."""
        alert_context = None
        if body.alert_id:
            detection_svc.ensure_alerts()
            alert_context = alert_svc.get_alert(body.alert_id)

        response = genai_svc.chat(
            user_message=body.message,
            alert_context=alert_context,
            conversation_history=body.conversation_history,
        )

        # Include suggested questions
        suggestions = genai_svc.get_suggested_questions(alert_context)

        result = response.to_dict()
        result["suggested_questions"] = suggestions
        return success_response(result)

    @r.post("/genai/explain-onboarding")
    @limiter.limit("30/minute")
    def explain_onboarding(
        request: Request,
        body: OnboardingExplainRequest,
        user: dict = Depends(require_permission("onboarding:read")),
        genai_svc: GenAIService = Depends(get_genai_service),
        onboarding_svc: OnboardingService = Depends(get_onboarding_service),
    ):
        """Generate plain-English explanation of onboarding risk assessment."""
        assessment_data = body.assessment_data
        if body.assessment_id and not assessment_data:
            assessment_data = onboarding_svc.get_assessment(body.assessment_id)
            if assessment_data is None:
                return error_response(
                    code="NOT_FOUND",
                    message=f"Assessment {body.assessment_id} not found",
                    status_code=404,
                )

        if not assessment_data:
            return error_response(
                code="BAD_REQUEST",
                message="Provide assessment_id or assessment_data",
                status_code=400,
            )

        response = genai_svc.explain_onboarding(assessment_data)
        return success_response(response.to_dict())

    @r.post("/genai/triage")
    @limiter.limit("30/minute")
    def triage_cluster(
        request: Request,
        body: TriageRequest,
        user: dict = Depends(require_permission("alerts:read")),
        genai_svc: GenAIService = Depends(get_genai_service),
    ):
        """Standalone GenAI triage for a single cluster."""
        result = genai_svc.triage_cluster(body.alert_data)
        return success_response(result.to_dict())

    @r.post("/genai/discover-patterns")
    @limiter.limit("10/minute")
    def discover_patterns(
        request: Request,
        body: PatternDiscoveryRequest,
        user: dict = Depends(require_permission("alerts:read")),
        genai_svc: GenAIService = Depends(get_genai_service),
        detection_svc: DetectionService = Depends(get_detection_service),
    ):
        """LLM-powered discovery of novel mule patterns in data."""
        detection_svc.ensure_alerts()
        dataset = detection_svc.get_or_generate_dataset()
        result = genai_svc.discover_patterns(
            transactions=dataset.get("transactions", []),
            accounts=dataset.get("accounts", []),
        )
        return success_response(result.to_dict())
