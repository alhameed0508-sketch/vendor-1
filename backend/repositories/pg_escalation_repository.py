"""
PostgreSQL-backed escalation repository.
Same interface as the in-memory EscalationRepository.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.engine import Engine
from infra.database.postgres import escalations

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> Dict:
    d = dict(row._mapping)
    for key in ("escalated_at", "resolved_at"):
        if d.get(key) is not None:
            d[key] = d[key].isoformat()
    return d


class PgEscalationRepository:
    """PostgreSQL escalation store with immutable update semantics."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def create(self, escalation: Dict) -> Dict:
        """Store a new escalation. Returns the stored escalation."""
        now = datetime.now(timezone.utc)
        values = {
            "escalation_id": escalation["escalation_id"],
            "alert_id": escalation.get("alert_id", ""),
            "reason": escalation.get("reason", ""),
            "priority": escalation.get("priority", "MEDIUM"),
            "status": escalation.get("status", "PENDING"),
            "user_id": escalation.get("user_id"),
            "escalated_at": now,
        }
        with self._engine.connect() as conn:
            conn.execute(escalations.insert().values(**values))
            conn.commit()
        return {**escalation, "escalated_at": now.isoformat()}

    def find_by_id(self, escalation_id: str) -> Optional[Dict]:
        """Find an escalation by ID. Returns a copy."""
        with self._engine.connect() as conn:
            row = conn.execute(
                escalations.select().where(
                    escalations.c.escalation_id == escalation_id
                )
            ).first()
        return _row_to_dict(row) if row else None

    def find_all(self, status: Optional[str] = None) -> List[Dict]:
        """List all escalations, optionally filtered by status."""
        query = escalations.select().order_by(
            escalations.c.escalated_at.desc()
        )
        if status:
            query = query.where(escalations.c.status == status.upper())
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        return [_row_to_dict(r) for r in rows]

    def update(self, escalation_id: str, **updates) -> Optional[Dict]:
        """Update escalation fields."""
        with self._engine.connect() as conn:
            row = conn.execute(
                escalations.select().where(
                    escalations.c.escalation_id == escalation_id
                )
            ).first()
            if row is None:
                return None

            conn.execute(
                escalations.update()
                .where(escalations.c.escalation_id == escalation_id)
                .values(**updates)
            )
            conn.commit()
        return self.find_by_id(escalation_id)
