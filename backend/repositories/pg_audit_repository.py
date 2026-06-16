"""
PostgreSQL-backed audit repository.
Same interface as the in-memory AuditRepository.
Append-only — no update or delete operations.
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy.engine import Engine
from infra.database.postgres import audit_logs

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> Dict:
    d = dict(row._mapping)
    if d.get("timestamp") is not None:
        d["timestamp"] = d["timestamp"].isoformat()
    return d


class PgAuditRepository:
    """Append-only PostgreSQL audit log."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def append(self, entry: Dict) -> Dict:
        """Append an audit entry. Returns a copy of the stored entry."""
        from datetime import datetime, timezone
        values = {
            "log_id": entry["log_id"],
            "action": entry.get("action", ""),
            "username": entry.get("user", entry.get("username", "")),
            "alert_id": entry.get("alert_id"),
            "details": entry.get("details"),
            "timestamp": entry.get("timestamp", datetime.now(timezone.utc).isoformat()),
        }
        # Parse timestamp string to datetime if needed
        ts = values["timestamp"]
        if isinstance(ts, str):
            from datetime import datetime as dt
            try:
                values["timestamp"] = dt.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                values["timestamp"] = datetime.now(timezone.utc)

        with self._engine.connect() as conn:
            conn.execute(audit_logs.insert().values(**values))
            conn.commit()
        return dict(entry)

    def find_all(
        self,
        alert_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Query audit entries with optional filters."""
        query = audit_logs.select().order_by(audit_logs.c.timestamp.desc())
        if alert_id:
            query = query.where(audit_logs.c.alert_id == alert_id)
        if action:
            query = query.where(audit_logs.c.action == action.upper())
        query = query.limit(limit)
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        results = []
        for row in rows:
            d = _row_to_dict(row)
            # Map 'username' column back to 'user' key for compatibility
            if "username" in d:
                d["user"] = d.pop("username")
            results.append(d)
        return results
