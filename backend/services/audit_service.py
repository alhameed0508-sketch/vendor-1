"""
Audit service — business logic for audit logging.
"""

import uuid
from datetime import datetime
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
        entry = {
            "log_id": f"LOG_{uuid.uuid4().hex[:8].upper()}",
            "action": action,
            "user": user,
            "alert_id": alert_id,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return self._repo.append(entry)

    def get_log(
        self,
        alert_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Query the audit trail with optional filters."""
        return self._repo.find_all(alert_id=alert_id, action=action, limit=limit)
