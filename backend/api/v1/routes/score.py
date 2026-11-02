"""Per-payment real-time scoring: POST /api/v1/score."""

import json

from api.deps import get_demo_replay, get_realtime_scorer
from api.v1.schemas.score import ScorePaymentRequest
from core.exceptions import ValidationError
from core.response import success_response
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from middleware.auth import require_role
from services.realtime_scorer import RealtimeScorer
from slowapi import Limiter

SCORE_ROLES = ("ADMIN", "SUPERVISOR", "INVESTIGATOR")
# Watching the synthetic replay changes nothing, so demo guests may too.
STREAM_ROLES = (*SCORE_ROLES, "GUEST")
ACTION_REVIEW = "route_to_human_review"
ACTION_NONE = "none"


def register_score_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register the real-time scoring route on the given router."""

    @r.post("")
    @limiter.limit("120/minute")
    def score_payment(
        request: Request,
        body: ScorePaymentRequest,
        user: dict = Depends(require_role(*SCORE_ROLES)),
        scorer: RealtimeScorer = Depends(get_realtime_scorer),
    ):
        """Score one payment in the context of the account network.

        Never blocks the payment: ``FLAG`` only routes the case to a human reviewer.
        Read-only against shared history, so callers cannot poison detection state.
        """
        try:
            result = scorer.score_payment(body.model_dump(), commit=False)
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

    @r.get("/stream")
    @limiter.limit("20/minute")
    def score_stream(
        request: Request,
        limit: int = Query(300, ge=1, le=2000),
        rate: float = Query(5.0, ge=0, le=100),
        user: dict = Depends(require_role(*STREAM_ROLES)),
        replay=Depends(get_demo_replay),
    ):
        """Server-sent events replaying synthetic payments through the scorer (demo only)."""

        def _sse():
            for event in replay.events(limit=limit, rate=rate):
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(_sse(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
