"""
STR Service — manages Suspicious Transaction Report lifecycle.
Handles creation, approval, submission to FINGate 2.0, and acknowledgement.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from repositories.str_repository import STRRepository

logger = logging.getLogger(__name__)


class STRService:
    """Manages STR lifecycle: create -> approve -> submit -> acknowledge."""

    def __init__(self, str_repo: STRRepository):
        self._repo = str_repo

    def create_str(
        self,
        alert_ids: List[str],
        account_ids: List[str],
        narrative: str,
        reporting_entity: str = "Indian Overseas Bank",
        prepared_by: str = "MuleCatch System",
        **extra_fields,
    ) -> Dict:
        """Create a new STR in DRAFT status."""
        str_id = f"STR-{uuid.uuid4().hex[:10].upper()}"
        record = {
            "str_id": str_id,
            "alert_ids": list(alert_ids),
            "account_ids": list(account_ids),
            "narrative": narrative,
            "reporting_entity": reporting_entity,
            "prepared_by": prepared_by,
            "fiu_reference": None,
            "submitted_at": None,
            "acknowledged_at": None,
            **extra_fields,
        }
        result = self._repo.create(record)
        logger.info("STR created: %s (alerts=%s)", str_id, alert_ids)
        return result

    def get_str(self, str_id: str) -> Optional[Dict]:
        return self._repo.get(str_id)

    def list_strs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict:
        records = self._repo.list_all(status=status, limit=limit, offset=offset)
        total = self._repo.count(status=status)
        return {
            "records": records,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def approve_for_submission(self, str_id: str, approved_by: str) -> Dict:
        """Supervisor approval — moves from DRAFT to READY_FOR_SUBMISSION."""
        result = self._repo.update_status(
            str_id,
            "READY_FOR_SUBMISSION",
            approved_by=approved_by,
            approved_at=datetime.now(timezone.utc).isoformat(),
        )
        if result is None:
            raise ValueError(f"STR not found: {str_id}")
        logger.info("STR approved: %s by %s", str_id, approved_by)
        return result

    def submit(self, str_id: str) -> Dict:
        """Submit to FINGate 2.0 (simulated). Moves to SUBMITTED."""
        now = datetime.now(timezone.utc)
        fiu_reference = f"FIU-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        result = self._repo.update_status(
            str_id,
            "SUBMITTED",
            fiu_reference=fiu_reference,
            submitted_at=now.isoformat(),
        )
        if result is None:
            raise ValueError(f"STR not found: {str_id}")
        logger.info("STR submitted: %s -> FINGate ref=%s", str_id, fiu_reference)
        return result

    def acknowledge(self, str_id: str) -> Dict:
        """Mark STR as acknowledged by FIU-IND."""
        result = self._repo.update_status(
            str_id,
            "ACKNOWLEDGED",
            acknowledged_at=datetime.now(timezone.utc).isoformat(),
        )
        if result is None:
            raise ValueError(f"STR not found: {str_id}")
        logger.info("STR acknowledged: %s", str_id)
        return result
