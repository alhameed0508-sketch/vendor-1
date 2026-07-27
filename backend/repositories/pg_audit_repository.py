"""
PostgreSQL-backed audit repository.
Same interface as the in-memory AuditRepository.
Append-only — no update or delete operations.
"""

import logging
import hashlib
import json
from typing import Dict, List, Optional

from sqlalchemy.engine import Engine
from backend.infra.database.postgres import audit_logs
from sqlalchemy import text

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
        """Atomically append an audit entry to the PostgreSQL hash chain."""
        from datetime import datetime, timezone

        with self._engine.connect() as conn:
            # Serialize audit writers across all API workers.
            conn.execute(text("SELECT pg_advisory_xact_lock(129743751)"))
            previous_hash = (
                conn.execute(
                    audit_logs.select()
                    .with_only_columns(audit_logs.c.entry_hash)
                    .order_by(audit_logs.c.timestamp.desc())
                    .limit(1)
                ).scalar()
                or ""
            )
            stored = {
                **entry,
                "previous_hash": previous_hash,
            }
            stored.pop("entry_hash", None)
            canonical = json.dumps(stored, sort_keys=True, separators=(",", ":"))
            stored["entry_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            values = {
                "log_id": stored["log_id"],
                "action": stored.get("action", ""),
                "username": stored.get("user", stored.get("username", "")),
                "alert_id": stored.get("alert_id"),
                "details": stored.get("details"),
                "previous_hash": stored["previous_hash"],
                "entry_hash": stored["entry_hash"],
                "timestamp": stored.get(
                    "timestamp", datetime.now(timezone.utc).isoformat()
                ),
            }
            ts = values["timestamp"]
            if isinstance(ts, str):
                from datetime import datetime as dt

                try:
                    values["timestamp"] = dt.fromisoformat(ts.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    values["timestamp"] = datetime.now(timezone.utc)
            conn.execute(audit_logs.insert().values(**values))
            conn.commit()
        return dict(stored)

    def latest_hash(self) -> str:
        """Return the newest audit entry hash."""
        query = (
            audit_logs.select()
            .with_only_columns(audit_logs.c.entry_hash)
            .order_by(audit_logs.c.timestamp.desc())
            .limit(1)
        )
        with self._engine.connect() as conn:
            value = conn.execute(query).scalar()
        return value or ""

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
