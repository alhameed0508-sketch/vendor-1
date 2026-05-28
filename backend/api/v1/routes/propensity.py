"""
Propensity score routes — /api/v1/propensity/*
"""

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter

from core.response import success_response, error_response
from middleware.auth import require_permission
from api.deps import get_propensity_scorer


def register_propensity_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register propensity score routes on the given router."""

    # IMPORTANT: Register more specific routes BEFORE path parameter routes
    # to avoid the path parameter matching literals like "top-risk"

    @r.get("/propensity/top-risk")
    @limiter.limit("30/minute")
    def get_top_risk(
        request: Request,
        limit: int = 50,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """Get top-risk accounts by propensity score."""
        scorer = get_propensity_scorer()
        records = scorer.get_top_risk(limit=limit)
        return success_response({
            "accounts": [
                {
                    "account_id": r.account_id,
                    "score": r.score,
                    "updated_at": r.updated_at,
                }
                for r in records
            ],
            "total": len(records),
        })

    @r.get("/propensity/{account_id}")
    @limiter.limit("100/minute")
    def get_propensity(
        request: Request,
        account_id: str,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """Get rolling propensity score for an account."""
        scorer = get_propensity_scorer()
        record = scorer.get_score(account_id)
        if record is None:
            return error_response(
                "NOT_FOUND",
                f"No propensity data for account {account_id}",
                status_code=404,
            )
        return success_response({
            "account_id": record.account_id,
            "score": record.score,
            "window_scores": dict(record.window_scores),
            "signal_breakdown": dict(record.signal_breakdown),
            "updated_at": record.updated_at,
        })
