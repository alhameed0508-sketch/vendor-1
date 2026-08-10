"""
Escalation service — escalation workflow business logic.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.exceptions import ConflictError, NotFoundError
from repositories.alert_repository import AlertRepository
from repositories.escalation_repository import EscalationRepository
from services.audit_service import AuditService


class EscalationService:
    """Business logic for escalation creation and resolution."""

    def __init__(
        self,
        escalation_repo: EscalationRepository,
        alert_repo: AlertRepository,
        audit_service: AuditService,
    ):
        self._repo = escalation_repo
        self._alert_repo = alert_repo
        self._audit = audit_service

    def create(
        self,
        alert_id: str,
        reason: str,
        priority: str,
        user_id: str,
    ) -> Dict:
        """Create a new escalation for an alert."""
        esc_id = f"ESC_{uuid.uuid4().hex[:8].upper()}"
        escalation = {
            "escalation_id": esc_id,
            "alert_id": alert_id,
            "reason": reason,
            "priority": priority,
            "status": "PENDING",
            "escalated_by": user_id,
            "escalated_at": datetime.now(timezone.utc).isoformat(),
            "resolved_by": None,
            "resolved_at": None,
            "action": None,
            "supervisor_notes": "",
        }
        result = self._repo.create(escalation)
        self._alert_repo.update(alert_id, status="UNDER_REVIEW")
        self._audit.log("ESCALATION_CREATED", user_id, alert_id, f"priority={priority}")
        return result

    def list_all(self, status: Optional[str] = None) -> List[Dict]:
        """List all escalations, optionally filtered by status."""
        return self._repo.find_all(status=status)

    def resolve(
        self,
        escalation_id: str,
        action: str,
        notes: str,
        user_id: str,
    ) -> Dict:
        """Supervisor acts on an escalation."""
        esc = self._repo.find_by_id(escalation_id)
        if not esc:
            raise NotFoundError("Escalation", escalation_id)
        if esc["status"] != "PENDING":
            raise ConflictError("Escalation already resolved")

        updated = self._repo.update(
            escalation_id,
            status=action,
            resolved_by=user_id,
            resolved_at=datetime.now(timezone.utc).isoformat(),
            supervisor_notes=notes,
        )

        self._audit.log("ESCALATION_RESOLVED", user_id, esc["alert_id"], f"action={action}")

        if action == "APPROVE":
            self._alert_repo.update(
                esc["alert_id"],
                status="UNDER_REVIEW",
                notes=f"Escalation approved: {notes}",
            )
        elif action == "REJECT":
            self._alert_repo.update(
                esc["alert_id"],
                status="RESOLVED",
                notes=f"Escalation rejected: {notes}",
            )

        return updated
