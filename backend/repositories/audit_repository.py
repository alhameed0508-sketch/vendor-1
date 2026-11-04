"""
Audit repository — append-only in-memory audit log.
"""

from threading import Lock
from typing import Dict, List, Optional


class AuditRepository:
    """Append-only audit log with immutable entries."""

    def __init__(self):
        self._entries: List[Dict] = []
        self._lock = Lock()

    def append(self, entry: Dict) -> Dict:
        """Append an audit entry. Returns a copy of the stored entry."""
        with self._lock:
            stored = dict(entry)
            self._entries.append(stored)
        return dict(stored)

    def latest_hash(self) -> str:
        """Return the current hash-chain head."""
        return self._entries[-1].get("entry_hash", "") if self._entries else ""

    def find_all(
        self,
        alert_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Query audit entries with optional filters."""
        # Newest first. Entries written within one clock tick share a timestamp (about 15 ms on Windows),
        # so the append order breaks ties; otherwise those entries would come back oldest first.
        result = [(i, dict(e)) for i, e in enumerate(self._entries)]
        if alert_id:
            result = [(i, e) for i, e in result if e.get("alert_id") == alert_id]
        if action:
            result = [(i, e) for i, e in result if e.get("action") == action.upper()]
        ordered = sorted(result, key=lambda p: (p[1]["timestamp"], p[0]), reverse=True)
        return [e for _, e in ordered[:limit]]
