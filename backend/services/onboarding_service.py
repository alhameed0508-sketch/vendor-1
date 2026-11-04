"""
Onboarding service — business logic for onboarding risk assessment.
Follows the ScreeningService pattern.
"""

import logging
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from repositories.onboarding_repository import OnboardingRepository

from models.onboarding.risk_scorer import assess_onboarding_risk

logger = logging.getLogger(__name__)


class OnboardingService:
    """Orchestrates onboarding risk assessment."""

    def __init__(
        self,
        onboarding_repo: OnboardingRepository,
        persistence=None,
        entity_resolver=None,
    ):
        self._repo = onboarding_repo
        self._persistence = persistence
        self._entity_resolver = entity_resolver

    def _make_graph_checker(self):
        """Create a graph checker callable if persistence layer is available."""
        if self._persistence is not None and hasattr(self._persistence, "find_flagged_neighbors"):
            return self._persistence.find_flagged_neighbors
        return None

    def assess_account(self, application: Dict) -> Dict:
        """Assess a single account application for mule risk."""
        resolution = None
        if self._entity_resolver is not None and (
            application.get("full_name")
            or application.get("phone_number")
            or application.get("government_id_hash")
            or application.get("device_fingerprint")
        ):
            resolution = self._entity_resolver.resolve_and_store(application)
            application = dict(application)
            application["similar_name_count"] = max(
                application.get("similar_name_count", 0),
                resolution["match_count"],
            )
        graph_checker = self._make_graph_checker()
        result = assess_onboarding_risk(application, graph_checker=graph_checker)
        result_dict = {
            "assessment_id": result.assessment_id,
            "account_id": result.account_id,
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
            "signals": list(result.signals),
            "reason_codes": list(result.reason_codes),
            "recommendation": result.recommendation,
            "assessed_at": result.assessed_at,
            "entity_resolution": resolution or {},
        }
        self._repo.store_assessment(result_dict)
        return result_dict

    def resolve_identity(self, profile: Dict) -> Dict:
        """Resolve and persist an identity without running full risk scoring."""
        if self._entity_resolver is None:
            raise RuntimeError("Entity resolution service is unavailable")
        return self._entity_resolver.resolve_and_store(profile)

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
        return self._repo.get_assessments(limit=limit, offset=offset, risk_level=risk_level)

    def get_stats(self) -> Dict:
        """Return aggregate onboarding statistics."""
        return self._repo.get_stats()
