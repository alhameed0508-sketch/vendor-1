"""Per-payment real-time scoring: POST /api/v1/score."""

from api.deps import get_realtime_scorer
from api.v1.schemas.score import ScorePaymentRequest
from core.exceptions import ValidationError
from core.response import success_response
from fastapi import APIRouter, Depends, Request
from middleware.auth import require_role
from services.realtime_scorer import RealtimeScorer
from slowapi import Limiter

SCORE_ROLES = ("ADMIN", "SUPERVISOR", "INVESTIGATOR")
ACTION_REVIEW = "route_to_human_review"
ACTION_NONE = "none"


def register_score_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register the real-time scoring route on the given router."""

    @r.post("")
    @limiter.limit("600/minute")
    def score_payment(
        request: Request,
        body: ScorePaymentRequest,
        user: dict = Depends(require_role(*SCORE_ROLES)),
        scorer: RealtimeScorer = Depends(get_realtime_scorer),
    ):
        """Score one payment in the context of the account network.

        Never blocks the payment: ``FLAG`` only routes the case to a human reviewer.
        """
        try:
            result = scorer.score_payment(body.model_dump())
        except ValueError as exc:
            raise ValidationError("Payment could not be scored", str(exc)) from exc
        return success_response(
            {
                "txn_id": result.txn_id,
                "risk_score": result.risk_score,
                "decision": result.decision,
                "action": ACTION_REVIEW if result.decision == "FLAG" else ACTION_NONE,
                "case_id": result.case_id,
                "ring_members": list(result.ring_members),
                "reasons": list(result.reasons),
                "latency_ms": result.latency_ms,
            }
        )
