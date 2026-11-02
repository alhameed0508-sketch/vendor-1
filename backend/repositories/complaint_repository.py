"""
Fraud complaint repository — in-memory store with immutable updates.
"""

from typing import Dict, List, Optional


class ComplaintRepository:
    """In-memory complaint store. Callers serialise writes (see ComplaintService)."""

    def __init__(self):
        self._complaints: Dict[str, Dict] = {}

    def create(self, complaint: Dict) -> Dict:
        """Store a new complaint. Returns the stored complaint."""
        self._complaints[complaint["complaint_id"]] = dict(complaint)
        return dict(complaint)

    def find_by_id(self, complaint_id: str) -> Optional[Dict]:
        """Find a complaint by ID. Returns a copy."""
        complaint = self._complaints.get(complaint_id)
        return dict(complaint) if complaint else None

    def find_all(self) -> List[Dict]:
        """List all complaints in the order they were filed."""
        return [dict(c) for c in self._complaints.values()]

    def count(self) -> int:
        return len(self._complaints)

    def update(self, complaint_id: str, **updates) -> Optional[Dict]:
        """Immutable update: creates new dict with merged changes."""
        complaint = self._complaints.get(complaint_id)
        if complaint is None:
            return None
        updated = {**complaint, **updates}
        self._complaints[complaint_id] = updated
        return dict(updated)
