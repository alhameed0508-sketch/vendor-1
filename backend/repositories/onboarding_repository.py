"""
Onboarding repository — in-memory data access for onboarding risk assessments.
Follows the ScreeningRepository pattern.
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class OnboardingRepository:
    """In-memory store for onboarding risk assessment results."""

    def __init__(self):
        self._assessments: List[Dict] = []

    def store_assessment(self, assessment: Dict) -> None:
        """Persist a single assessment result."""
        self._assessments.append(assessment)

    def get_assessment(self, assessment_id: str) -> Optional[Dict]:
        """Retrieve a single assessment by ID."""
        for a in self._assessments:
            if a.get("assessment_id") == assessment_id:
                return a
        return None

    def get_assessments(
        self,
        limit: int = 50,
        offset: int = 0,
        risk_level: Optional[str] = None,
    ) -> List[Dict]:
        """List assessments with optional filtering by risk level."""
        results = self._assessments
        if risk_level:
            results = [a for a in results if a.get("risk_level") == risk_level]
        # Return newest first
        results = list(reversed(results))
        return results[offset : offset + limit]

    def get_stats(self) -> Dict:
        """Return aggregate statistics."""
        total = len(self._assessments)
        levels = {}
        for a in self._assessments:
            lvl = a.get("risk_level", "UNKNOWN")
            levels[lvl] = levels.get(lvl, 0) + 1

        high_risk = levels.get("HIGH", 0) + levels.get("CRITICAL", 0)
        blocked = sum(1 for a in self._assessments if a.get("recommendation", "").startswith("BLOCK"))
        pass_rate = round((total - high_risk) / total, 4) if total > 0 else 1.0

        return {
            "total_assessed": total,
            "high_risk_flagged": high_risk,
            "auto_blocked": blocked,
            "pass_rate": pass_rate,
            "by_level": levels,
        }
