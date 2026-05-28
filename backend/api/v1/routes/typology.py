"""
Typology routes — /api/v1/typology/*

Exposes mule typology classification and aggregate distribution endpoints.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter

from core.response import success_response, error_response
from middleware.auth import require_permission
from models.typology.mule_classifier import MuleTypologyClassifier, MuleTypology
from models.typology.response_orchestrator import ResponseOrchestrator


# Module-level singletons (stateless classifiers, safe to share)
_classifier = MuleTypologyClassifier()
_orchestrator = ResponseOrchestrator()

# In-memory store for demo/testing — in production, backed by a database
_flagged_accounts: dict = {}


def _get_sample_accounts() -> dict:
    """Return the in-memory flagged account store.

    In a real deployment this would query the account repository.
    Populated lazily with sample data if empty.
    """
    if not _flagged_accounts:
        _flagged_accounts.update({
            "AC_DEMO_001": {
                "account": {
                    "account_id": "AC_DEMO_001",
                    "onboarding_time_seconds": 90,
                    "kyc_completeness": 0.98,
                    "account_age_days": 5,
                },
                "transactions": [
                    {"amount": 200000, "timestamp": 1000, "is_incoming": False,
                     "beneficiary_id": "B1"},
                    {"amount": 300000, "timestamp": 2000, "is_incoming": False,
                     "beneficiary_id": "B2"},
                ],
                "session_data": {"unique_devices": 3},
            },
            "AC_DEMO_002": {
                "account": {
                    "account_id": "AC_DEMO_002",
                    "account_age_days": 180,
                    "kyc_completeness": 0.85,
                },
                "transactions": [
                    {"amount": 1000, "timestamp": 1000, "is_incoming": False,
                     "beneficiary_id": "B1"},
                    {"amount": 1200, "timestamp": 100000, "is_incoming": False,
                     "beneficiary_id": "B1"},
                    {"amount": 500000, "timestamp": 6000000, "is_incoming": False,
                     "beneficiary_id": "B3"},
                    {"amount": 600000, "timestamp": 6100000, "is_incoming": False,
                     "beneficiary_id": "B4"},
                ],
                "session_data": None,
            },
        })
    return _flagged_accounts


def register_typology_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register typology classification routes on the given router."""

    @r.get("/typology/distribution")
    @limiter.limit("30/minute")
    def get_typology_distribution(
        request: Request,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """Aggregate typology distribution across all flagged accounts."""
        accounts = _get_sample_accounts()

        distribution: dict = {t.value: 0 for t in MuleTypology}
        results = []

        for acct_id, data in accounts.items():
            result = _classifier.classify(
                data["account"],
                data["transactions"],
                data.get("session_data"),
            )
            distribution[result.predicted_type.value] += 1
            results.append({
                "account_id": result.account_id,
                "predicted_type": result.predicted_type.value,
                "confidence": result.confidence,
            })

        return success_response({
            "distribution": distribution,
            "total_flagged": len(accounts),
            "accounts": results,
        })

    @r.get("/typology/{account_id}")
    @limiter.limit("60/minute")
    def classify_account(
        request: Request,
        account_id: str,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """Classify a single account into one of five mule typologies."""
        accounts = _get_sample_accounts()
        data = accounts.get(account_id)

        if data is None:
            return error_response(
                "NOT_FOUND",
                f"No flagged account data for {account_id}",
                status_code=404,
            )

        result = _classifier.classify(
            data["account"],
            data["transactions"],
            data.get("session_data"),
        )

        actions = _orchestrator.orchestrate_response(result)

        return success_response({
            "account_id": result.account_id,
            "predicted_type": result.predicted_type.value,
            "confidence": result.confidence,
            "probabilities": result.probabilities,
            "behavioral_signals": result.behavioral_signals,
            "reason_codes": list(result.reason_codes),
            "response_actions": [
                {
                    "action_type": a.action_type,
                    "urgency": a.urgency,
                    "notification_targets": list(a.notification_targets),
                    "investigation_priority": a.investigation_priority,
                    "description": a.description,
                }
                for a in actions
            ],
        })
