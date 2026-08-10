"""
Audit service — business logic for audit logging.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from repositories.audit_repository import AuditRepository


class AuditService:
    """Immutable audit logging service."""

    def __init__(self, audit_repo: AuditRepository):
        self._repo = audit_repo

    def log(
        self,
        action: str,
        user: str,
        alert_id: Optional[str] = None,
        details: str = "",
    ) -> Dict:
        """Create an immutable audit entry."""
        previous_hash = self._repo.latest_hash()
        entry = {
            "log_id": f"LOG_{uuid.uuid4().hex[:8].upper()}",
            "action": action,
            "user": user,
            "alert_id": alert_id,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_hash": previous_hash,
        }
        canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        entry["entry_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self._repo.append(entry)

    def get_log(
        self,
        alert_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Query the audit trail with optional filters."""
        return self._repo.find_all(alert_id=alert_id, action=action, limit=limit)

    def verify_integrity(self) -> Dict:
        """Verify the retained audit chain from oldest to newest."""
        entries = self._repo.find_all(limit=100_000)
        by_previous = {}
        for entry in entries:
            previous = entry.get("previous_hash", "")
            if previous in by_previous:
                return {
                    "valid": False,
                    "checked": 0,
                    "reason": "forked_chain",
                }
            by_previous[previous] = entry

        previous_hash = ""
        checked = 0
        while previous_hash in by_previous:
            entry = by_previous[previous_hash]
            expected_hash = entry.get("entry_hash", "")
            payload = dict(entry)
            payload.pop("entry_hash", None)
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if not expected_hash or actual_hash != expected_hash:
                return {
                    "valid": False,
                    "checked": checked,
                    "reason": "entry_hash",
                }
            previous_hash = expected_hash
            checked += 1

        if checked != len(entries):
            return {
                "valid": False,
                "checked": checked,
                "reason": "disconnected_chain",
            }
        return {"valid": True, "checked": checked, "head_hash": previous_hash}
