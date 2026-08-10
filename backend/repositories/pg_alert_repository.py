"""
PostgreSQL-backed alert repository.
Same interface as AlertRepository. Alerts are stored as a JSONB payload
(mirroring the Neo4j payload_json convention) plus a few queryable columns.
store_batch() replaces the full alert set, matching in-memory list-replace
semantics used by the detection pipeline.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.engine import Engine

from backend.infra.database.postgres import alerts_table

logger = logging.getLogger(__name__)


def _row_to_alert(row) -> Dict:
    d = dict(row._mapping)
    payload = dict(d.get("payload") or {})
    payload["status"] = d.get("status", payload.get("status", "OPEN"))
    payload["investigator_notes"] = d.get("investigator_notes", payload.get("investigator_notes", ""))
    return payload


class PgAlertRepository:
    """PostgreSQL data access for alerts."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def find_all(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        query = alerts_table.select().order_by(alerts_table.c.created_at.desc())
        if severity:
            query = query.where(alerts_table.c.severity == severity.upper())
        if status:
            query = query.where(alerts_table.c.status == status.upper())
        query = query.limit(limit)
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        return [_row_to_alert(r) for r in rows]

    def find_by_id(self, alert_id: str) -> Optional[Dict]:
        with self._engine.connect() as conn:
            row = conn.execute(alerts_table.select().where(alerts_table.c.alert_id == alert_id)).first()
        return _row_to_alert(row) if row else None

    def store_batch(self, alerts: List[Dict]) -> None:
        """Replace the full alert set with the given batch."""
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(alerts_table.delete())
            if not alerts:
                return
            rows = [
                {
                    "alert_id": a["alert_id"],
                    "severity": a.get("severity", "MEDIUM"),
                    "status": a.get("status", "OPEN"),
                    "investigator_notes": a.get("investigator_notes", ""),
                    "payload": a,
                    "created_at": now,
                    "updated_at": now,
                }
                for a in alerts
            ]
            conn.execute(alerts_table.insert(), rows)

    def update(
        self,
        alert_id: str,
        status: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Dict]:
        values = {"updated_at": datetime.now(timezone.utc)}
        if status is not None:
            values["status"] = status
        if notes is not None:
            values["investigator_notes"] = notes
        with self._engine.begin() as conn:
            conn.execute(alerts_table.update().where(alerts_table.c.alert_id == alert_id).values(**values))
            row = conn.execute(alerts_table.select().where(alerts_table.c.alert_id == alert_id)).first()
        return _row_to_alert(row) if row else None
