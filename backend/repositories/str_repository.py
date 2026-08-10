"""
STR (Suspicious Transaction Report) Repository
================================================
In-memory store with status tracking for STR lifecycle management.
Status progression: DRAFT -> READY_FOR_SUBMISSION -> SUBMITTED -> ACKNOWLEDGED
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

VALID_STATUSES = ("DRAFT", "READY_FOR_SUBMISSION", "SUBMITTED", "ACKNOWLEDGED")

VALID_TRANSITIONS = {
    "DRAFT": ("READY_FOR_SUBMISSION",),
    "READY_FOR_SUBMISSION": ("SUBMITTED", "DRAFT"),
    "SUBMITTED": ("ACKNOWLEDGED",),
    "ACKNOWLEDGED": (),
}


class STRRepository:
    """In-memory STR storage with status tracking."""

    def __init__(self):
        self._store: Dict[str, Dict] = {}

    def create(self, str_record: Dict) -> Dict:
        str_id = str_record["str_id"]
        record = {
            **str_record,
            "status": "DRAFT",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._store[str_id] = record
        return dict(record)

    def get(self, str_id: str) -> Optional[Dict]:
        record = self._store.get(str_id)
        return dict(record) if record else None

    def list_all(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        records = list(self._store.values())
        if status:
            records = [r for r in records if r.get("status") == status]
        records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return [dict(r) for r in records[offset : offset + limit]]

    def update_status(self, str_id: str, new_status: str, **kwargs) -> Optional[Dict]:
        record = self._store.get(str_id)
        if record is None:
            return None

        current = record.get("status", "DRAFT")
        if new_status not in VALID_TRANSITIONS.get(current, ()):
            raise ValueError(
                f"Invalid status transition: {current} -> {new_status}. Allowed: {VALID_TRANSITIONS.get(current, ())}"
            )

        updated = {
            **record,
            "status": new_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        self._store[str_id] = updated
        return dict(updated)

    def count(self, status: Optional[str] = None) -> int:
        if status:
            return sum(1 for r in self._store.values() if r.get("status") == status)
        return len(self._store)
