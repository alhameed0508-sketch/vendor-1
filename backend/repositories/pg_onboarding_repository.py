"""
PostgreSQL-backed onboarding repository.
Same interface as the in-memory OnboardingRepository.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from infra.database.postgres import onboarding_assessments

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> Dict:
    d = dict(row._mapping)
    if d.get("assessed_at") is not None:
        d["assessed_at"] = d["assessed_at"].isoformat()
    return d


class PgOnboardingRepository:
    """PostgreSQL store for onboarding risk assessment results."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def store_assessment(self, assessment: Dict) -> None:
        """Persist a single assessment result."""
        now = datetime.now(timezone.utc)
        values = {
            "assessment_id": assessment.get("assessment_id", ""),
            "account_id": assessment.get("account_id", ""),
            "risk_score": assessment.get("risk_score", 0),
            "risk_level": assessment.get("risk_level", "LOW"),
            "signals": assessment.get("signals", []),
            "reason_codes": assessment.get("reason_codes", []),
            "recommendation": assessment.get("recommendation", ""),
            "assessed_at": now,
        }
        with self._engine.connect() as conn:
            conn.execute(onboarding_assessments.insert().values(**values))
            conn.commit()

    def get_assessment(self, assessment_id: str) -> Optional[Dict]:
        """Retrieve a single assessment by ID."""
        with self._engine.connect() as conn:
            row = conn.execute(
                onboarding_assessments.select().where(
                    onboarding_assessments.c.assessment_id == assessment_id
                )
            ).first()
        return _row_to_dict(row) if row else None

    def get_assessments(
        self,
        limit: int = 50,
        offset: int = 0,
        risk_level: Optional[str] = None,
    ) -> List[Dict]:
        """List assessments with optional filtering by risk level."""
        query = onboarding_assessments.select().order_by(
            onboarding_assessments.c.assessed_at.desc()
        )
        if risk_level:
            query = query.where(
                onboarding_assessments.c.risk_level == risk_level
            )
        query = query.limit(limit).offset(offset)
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_stats(self) -> Dict:
        """Return aggregate statistics."""
        t = onboarding_assessments
        with self._engine.connect() as conn:
            total = conn.execute(
                select(func.count()).select_from(t)
            ).scalar() or 0

            level_rows = conn.execute(
                select(t.c.risk_level, func.count().label("cnt"))
                .group_by(t.c.risk_level)
            ).fetchall()

            blocked = conn.execute(
                select(func.count()).select_from(t)
                .where(t.c.recommendation.like("BLOCK%"))
            ).scalar() or 0

        levels = {r._mapping["risk_level"]: r._mapping["cnt"] for r in level_rows}
        high_risk = levels.get("HIGH", 0) + levels.get("CRITICAL", 0)
        pass_rate = round((total - high_risk) / total, 4) if total > 0 else 1.0

        return {
            "total_assessed": total,
            "high_risk_flagged": high_risk,
            "auto_blocked": blocked,
            "pass_rate": pass_rate,
            "by_level": levels,
        }
