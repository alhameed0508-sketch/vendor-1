"""
Investigation repository — in-memory store with immutable updates.
"""

from threading import Lock
from typing import Dict, List, Optional


class InvestigationRepository:
    """In-memory investigation store. Returns copies; updates replace the stored record."""

    def __init__(self):
        self._items: Dict[str, Dict] = {}
        self._lock = Lock()

    def create(self, investigation: Dict) -> Dict:
        with self._lock:
            self._items[investigation["investigation_id"]] = dict(investigation)
        return dict(investigation)

    def find_by_id(self, investigation_id: str) -> Optional[Dict]:
        item = self._items.get(investigation_id)
        return dict(item) if item else None

    def find_by_source(self, source: str, source_id: str, institution_id: Optional[str] = None) -> Optional[Dict]:
        """The investigation for a case inside one institution, so banks never see each other's duplicates."""
        for item in self._items.values():
            if (
                item["source"] == source
                and item["source_id"] == source_id
                and item.get("institution_id") == institution_id
            ):
                return dict(item)
        return None

    def find_all(self) -> List[Dict]:
        return sorted((dict(i) for i in self._items.values()), key=lambda i: i["opened_at"], reverse=True)

    def update(self, investigation_id: str, **updates) -> Optional[Dict]:
        with self._lock:
            item = self._items.get(investigation_id)
            if item is None:
                return None
            updated = {**item, **updates}
            self._items[investigation_id] = updated
        return dict(updated)
