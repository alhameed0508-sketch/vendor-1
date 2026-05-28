"""
Investigation routes — /api/v1/investigation/*
Agentic AI investigation: case assembly, STR narrative, priority queue, copilot.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from slowapi import Limiter

from core.response import success_response, error_response
from middleware.auth import require_permission
from api.deps import get_genai_service
from services.genai_service import GenAIService
from services.investigation.case_assembler import CaseAssemblyAgent
from services.investigation.narrative_agent import NarrativeAgent
from models.investigation.priority_scorer import AlertPriorityScorer


class CaseAssembleRequest(BaseModel):
    alert_data: dict = Field(..., description="Full alert data for case assembly")
    transactions: Optional[List[dict]] = None
    accounts: Optional[List[dict]] = None


class NarrativeRequest(BaseModel):
    alert_data: dict = Field(..., description="Full alert data for narrative generation")
    transactions: Optional[List[dict]] = None
    accounts: Optional[List[dict]] = None


class PriorityQueueRequest(BaseModel):
    alerts: List[dict] = Field(..., description="List of alerts to score and rank")


class CopilotRequest(BaseModel):
    alert_id: str
    question: str
    case_context: Optional[dict] = None


def register_investigation_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register investigation routes on the given router."""

    @r.post("/assemble/{alert_id}")
    @limiter.limit("30/minute")
    def assemble_case(
        request: Request,
        alert_id: str,
        body: CaseAssembleRequest,
        user: dict = Depends(require_permission("alerts:read")),
        genai_svc: GenAIService = Depends(get_genai_service),
    ):
        """Trigger case assembly — gathers all evidence into a structured case file."""
        agent = CaseAssemblyAgent(genai_service=genai_svc)
        case_file = agent.assemble_case(
            alert_id=alert_id,
            alert_data=body.alert_data,
            transactions=body.transactions,
            accounts=body.accounts,
        )
        # Convert frozen dataclass to dict
        return success_response({
            "alert_id": case_file.alert_id,
            "account_ids": list(case_file.account_ids),
            "transaction_summary": case_file.transaction_summary,
            "graph_context": case_file.graph_context,
            "behavioral_profile": case_file.behavioral_profile,
            "screening_results": case_file.screening_results,
            "typology": case_file.typology,
            "timeline": list(case_file.timeline),
            "evidence_items": [
                {
                    "evidence_type": e.evidence_type,
                    "description": e.description,
                    "data": e.data,
                    "severity": e.severity,
                }
                for e in case_file.evidence_items
            ],
            "created_at": case_file.created_at,
            "case_strength": case_file.case_strength,
        })

    @r.post("/narrative/{alert_id}")
    @limiter.limit("20/minute")
    def generate_narrative(
        request: Request,
        alert_id: str,
        body: NarrativeRequest,
        user: dict = Depends(require_permission("alerts:read")),
        genai_svc: GenAIService = Depends(get_genai_service),
    ):
        """Generate FIU-IND compliant STR narrative for an alert."""
        assembler = CaseAssemblyAgent(genai_service=genai_svc)
        case_file = assembler.assemble_case(
            alert_id=alert_id,
            alert_data=body.alert_data,
            transactions=body.transactions,
            accounts=body.accounts,
        )

        narrator = NarrativeAgent(genai_service=genai_svc)
        narrative = narrator.generate_str_narrative(case_file)
        validation = narrator.validate_narrative(narrative)

        result = narrative.to_dict()
        result["validation"] = validation
        return success_response(result)

    @r.post("/priority-queue")
    @limiter.limit("30/minute")
    def priority_queue(
        request: Request,
        body: PriorityQueueRequest,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """Get priority-sorted investigation queue."""
        if not body.alerts:
            return error_response(
                code="BAD_REQUEST",
                message="No alerts provided for priority scoring",
                status_code=400,
            )

        scorer = AlertPriorityScorer()
        results = scorer.score_queue(body.alerts)
        return success_response([r.to_dict() for r in results])

    @r.post("/copilot")
    @limiter.limit("60/minute")
    def investigation_copilot(
        request: Request,
        body: CopilotRequest,
        user: dict = Depends(require_permission("alerts:read")),
        genai_svc: GenAIService = Depends(get_genai_service),
    ):
        """Natural language investigation query — uses GenAI copilot."""
        response = genai_svc.investigate_query(
            alert_id=body.alert_id,
            question=body.question,
            case_context=body.case_context,
        )
        result = response.to_dict()

        # Include next step suggestions when context is available
        if body.case_context:
            suggestions = genai_svc.suggest_next_steps(body.case_context)
            result["suggested_next_steps"] = suggestions.message

        return success_response(result)
