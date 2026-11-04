"""
Escalation repository — in-memory store with immutable updates.
"""

from typing import Dict, List, Optional


class EscalationRepository:
    """Thread-safe in-memory escalation store using immutable patterns."""

    def __init__(self):
        self._escalations: Dict[str, Dict] = {}

    def create(self, escalation: Dict) -> Dict:
        """Store a new escalation. Returns the stored escalation."""
        esc_id = escalation["escalation_id"]
        self._escalations[esc_id] = dict(escalation)
        return dict(escalation)

    def find_by_id(self, escalation_id: str) -> Optional[Dict]:
        """Find an escalation by ID. Returns a copy."""
        esc = self._escalations.get(escalation_id)
        return dict(esc) if esc else None

    def find_all(self, status: Optional[str] = None) -> List[Dict]:
        """List all escalations, optionally filtered by status."""
        result = [dict(e) for e in self._escalations.values()]
        if status:
            result = [e for e in result if e["status"] == status.upper()]
        return sorted(result, key=lambda e: e["escalated_at"], reverse=True)

    def update(self, escalation_id: str, **updates) -> Optional[Dict]:
        """Immutable update: creates new dict with merged changes."""
        esc = self._escalations.get(escalation_id)
        if esc is None:
            return None
        updated = {**esc, **updates}
        self._escalations[escalation_id] = updated
        return dict(updated)
