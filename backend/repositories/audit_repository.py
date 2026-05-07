"""
Audit repository — append-only in-memory audit log.
"""

from typing import Dict, List, Optional


class AuditRepository:
    """Append-only audit log with immutable entries."""

    def __init__(self):
        self._entries: List[Dict] = []

    def append(self, entry: Dict) -> Dict:
        """Append an audit entry. Returns a copy of the stored entry."""
        stored = dict(entry)
        self._entries.append(stored)
        return dict(stored)

    def find_all(
        self,
        alert_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Query audit entries with optional filters."""
        result = [dict(e) for e in self._entries]
        if alert_id:
            result = [e for e in result if e.get("alert_id") == alert_id]
        if action:
            result = [e for e in result if e.get("action") == action.upper()]
        return sorted(result, key=lambda e: e["timestamp"], reverse=True)[:limit]
