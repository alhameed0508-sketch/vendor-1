"""
Onboarding service — business logic for onboarding risk assessment.
Follows the ScreeningService pattern.
"""

import logging
import sys
import os
from dataclasses import asdict
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from repositories.onboarding_repository import OnboardingRepository
from models.onboarding.risk_scorer import assess_onboarding_risk

logger = logging.getLogger(__name__)


class OnboardingService:
    """Orchestrates onboarding risk assessment."""

    def __init__(self, onboarding_repo: OnboardingRepository):
        self._repo = onboarding_repo

    def assess_account(self, application: Dict) -> Dict:
        """Assess a single account application for mule risk."""
        result = assess_onboarding_risk(application)
        result_dict = {
            "assessment_id": result.assessment_id,
            "account_id": result.account_id,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "signals": list(result.signals),
            "reason_codes": list(result.reason_codes),
            "recommendation": result.recommendation,
            "assessed_at": result.assessed_at,
        }
        self._repo.store_assessment(result_dict)
        return result_dict

    def assess_batch(self, applications: List[Dict]) -> List[Dict]:
        """Assess multiple account applications."""
        results = []
        for app in applications:
            result = self.assess_account(app)
            results.append(result)
        logger.info("Batch onboarding assessment: %d applications processed", len(results))
        return results

    def get_assessment(self, assessment_id: str) -> Optional[Dict]:
        """Retrieve a single assessment by ID."""
        return self._repo.get_assessment(assessment_id)

    def get_assessments(
        self,
        limit: int = 50,
        offset: int = 0,
        risk_level: Optional[str] = None,
    ) -> List[Dict]:
        """List assessments with optional filtering."""
        return self._repo.get_assessments(
            limit=limit, offset=offset, risk_level=risk_level
        )

    def get_stats(self) -> Dict:
        """Return aggregate onboarding statistics."""
        return self._repo.get_stats()
