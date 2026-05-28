"""
Scam detection routes — /api/v1/scam/*

Real-time sender-side victim detection and dual-sided transaction evaluation.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from slowapi import Limiter

# Ensure parent paths are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from core.response import error_response, success_response
from middleware.auth import require_permission
from models.scam.dual_risk_engine import DualRiskEngine
from models.scam.victim_detector import ScamVictimDetector

router = APIRouter(tags=["scam"])

# Module-level instances (stateless detectors, safe to share)
_victim_detector = ScamVictimDetector()
_dual_engine = DualRiskEngine(victim_detector=_victim_detector)

# In-memory store for recent evaluations (production would use a database)
_recent_evaluations: List[Dict] = []
_MAX_STORED = 500


# ── Request Schemas ─────────────────────────────────────────────────────

class EvaluateTransactionRequest(BaseModel):
    """Request body for dual-sided transaction evaluation."""

    sender: Dict = Field(..., description="Sender account details")
    receiver: Dict = Field(..., description="Receiver account details")
    transaction: Dict = Field(..., description="Transaction details")
    session_context: Optional[Dict] = Field(
        None, description="Real-time session telemetry",
    )
    sender_history: Optional[List[Dict]] = Field(
        None, description="Sender's historical transactions",
    )
    receiver_mule_score: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Mule probability from existing pipeline",
    )


class InterveneRequest(BaseModel):
    """Request body for manual intervention trigger."""

    action: str = Field(
        ..., description="Intervention action: BLOCK, DELAY, WARN, RELEASE",
    )
    reason: str = Field("", description="Reason for the intervention")


# ── Route Registration ──────────────────────────────────────────────────

def register_scam_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register scam detection routes on the given router."""

    @r.post("/evaluate-transaction")
    @limiter.limit("30/minute")
    def evaluate_transaction(
        request: Request,
        body: EvaluateTransactionRequest,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """Real-time dual-sided transaction evaluation.

        Scores both sender (victim risk) and receiver (mule risk) and
        returns a combined risk assessment with intervention recommendation.
        """
        result = _dual_engine.evaluate_transaction(
            sender=body.sender,
            receiver=body.receiver,
            transaction=body.transaction,
            session_context=body.session_context,
            sender_history=body.sender_history,
            receiver_mule_score=body.receiver_mule_score,
        )

        evaluation_record = {
            "evaluation_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sender_account": body.sender.get("account_id", "UNKNOWN"),
            "receiver_account": body.receiver.get("account_id", "UNKNOWN"),
            "sender_victim_score": result.sender_risk.composite_score,
            "receiver_mule_score": body.receiver_mule_score,
            "combined_risk": result.combined_risk,
            "recommendation": result.transaction_recommendation,
            "intervention_message": result.intervention_message,
            "reason_codes": list(result.reason_codes),
            "status": "PENDING",
        }

        # Store for victim-alerts endpoint
        _recent_evaluations.insert(0, evaluation_record)
        if len(_recent_evaluations) > _MAX_STORED:
            del _recent_evaluations[_MAX_STORED:]

        return success_response({
            "evaluation_id": evaluation_record["evaluation_id"],
            "sender_risk": {
                "account_id": result.sender_risk.account_id,
                "victim_probability": result.sender_risk.victim_probability,
                "coaching_indicators": list(result.sender_risk.coaching_indicators),
                "session_anomalies": list(result.sender_risk.session_anomalies),
                "recommended_intervention": result.sender_risk.recommended_intervention,
                "reason_codes": list(result.sender_risk.reason_codes),
                "score_breakdown": result.sender_risk.score_breakdown,
            },
            "receiver_risk": result.receiver_risk,
            "combined_risk": result.combined_risk,
            "transaction_recommendation": result.transaction_recommendation,
            "intervention_message": result.intervention_message,
            "reason_codes": list(result.reason_codes),
        })

    @r.get("/victim-alerts")
    @limiter.limit("60/minute")
    def victim_alerts(
        request: Request,
        min_score: float = 0.3,
        limit: int = 50,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """List recent potential scam victim evaluations.

        Returns evaluations where the sender's victim score exceeds
        the min_score threshold, ordered by most recent first.
        """
        filtered = [
            e for e in _recent_evaluations
            if e["sender_victim_score"] >= min_score
        ][:limit]
        return success_response(filtered)

    @r.post("/intervene/{transaction_id}")
    @limiter.limit("20/minute")
    def intervene(
        request: Request,
        transaction_id: str,
        body: InterveneRequest,
        user: dict = Depends(require_permission("alerts:write")),
    ):
        """Trigger a manual intervention for a flagged transaction.

        Actions: BLOCK, DELAY, WARN, RELEASE
        """
        valid_actions = {"BLOCK", "DELAY", "WARN", "RELEASE"}
        if body.action not in valid_actions:
            return error_response(
                code="INVALID_ACTION",
                message=f"Action must be one of: {', '.join(sorted(valid_actions))}",
                status_code=400,
            )

        # Find the evaluation
        target = None
        for evaluation in _recent_evaluations:
            if evaluation["evaluation_id"] == transaction_id:
                target = evaluation
                break

        if target is None:
            return error_response(
                code="NOT_FOUND",
                message=f"Evaluation {transaction_id} not found",
                status_code=404,
            )

        # Update status (mutating the stored dict — in production, this
        # would be a database update returning a new record)
        intervention_record = {
            **target,
            "status": body.action,
            "intervention_by": user.get("sub", "unknown"),
            "intervention_reason": body.reason,
            "intervention_at": datetime.now(timezone.utc).isoformat(),
        }

        # Replace in list
        for i, evaluation in enumerate(_recent_evaluations):
            if evaluation["evaluation_id"] == transaction_id:
                _recent_evaluations[i] = intervention_record
                break

        return success_response(intervention_record)
