"""
PostgreSQL-backed STR repository.
Same interface as the in-memory STRRepository.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.engine import Engine
from backend.infra.database.postgres import str_reports

logger = logging.getLogger(__name__)

VALID_STATUSES = ("DRAFT", "READY_FOR_SUBMISSION", "SUBMITTED", "ACKNOWLEDGED")

VALID_TRANSITIONS = {
    "DRAFT": ("READY_FOR_SUBMISSION",),
    "READY_FOR_SUBMISSION": ("SUBMITTED", "DRAFT"),
    "SUBMITTED": ("ACKNOWLEDGED",),
    "ACKNOWLEDGED": (),
}


def _row_to_dict(row) -> Dict:
    d = dict(row._mapping)
    for key in ("created_at", "updated_at", "submitted_at", "acknowledged_at"):
        if d.get(key) is not None:
            d[key] = d[key].isoformat()
    return d


class PgSTRRepository:
    """PostgreSQL STR storage with status tracking."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def create(self, str_record: Dict) -> Dict:
        now = datetime.now(timezone.utc)
        values = {
            "str_id": str_record["str_id"],
            "alert_ids": str_record.get("alert_ids", []),
            "account_ids": str_record.get("account_ids", []),
            "status": "DRAFT",
            "narrative": str_record.get("narrative", ""),
            "total_amount": str_record.get("total_amount", 0),
            "risk_score": str_record.get("risk_score", 0),
            "gnn_score": str_record.get("gnn_score"),
            "reason_codes": str_record.get("reason_codes", []),
            "reporting_entity": str_record.get("reporting_entity", ""),
            "reporting_ifsc": str_record.get("reporting_ifsc", ""),
            "prepared_by": str_record.get("prepared_by", ""),
            "fiu_format_version": str_record.get("fiu_format_version"),
            "created_at": now,
            "updated_at": now,
        }
        with self._engine.connect() as conn:
            conn.execute(str_reports.insert().values(**values))
            conn.commit()
        return {**str_record, "status": "DRAFT", "created_at": now.isoformat()}

    def get(self, str_id: str) -> Optional[Dict]:
        with self._engine.connect() as conn:
            row = conn.execute(
                str_reports.select().where(str_reports.c.str_id == str_id)
            ).first()
        return _row_to_dict(row) if row else None

    def list_all(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        query = str_reports.select().order_by(str_reports.c.created_at.desc())
        if status:
            query = query.where(str_reports.c.status == status)
        query = query.limit(limit).offset(offset)
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        return [_row_to_dict(r) for r in rows]

    def update_status(self, str_id: str, new_status: str, **kwargs) -> Optional[Dict]:
        with self._engine.connect() as conn:
            row = conn.execute(
                str_reports.select().where(str_reports.c.str_id == str_id)
            ).first()
            if row is None:
                return None

            current = row._mapping["status"]
            if new_status not in VALID_TRANSITIONS.get(current, ()):
                raise ValueError(
                    f"Invalid status transition: {current} -> {new_status}. "
                    f"Allowed: {VALID_TRANSITIONS.get(current, ())}"
                )

            update_values = {
                "status": new_status,
                "updated_at": datetime.now(timezone.utc),
                **kwargs,
            }
            conn.execute(
                str_reports.update()
                .where(str_reports.c.str_id == str_id)
                .values(**update_values)
            )
            conn.commit()

        return self.get(str_id)

    def count(self, status: Optional[str] = None) -> int:
        from sqlalchemy import func

        query = str_reports.select().with_only_columns(func.count())
        if status:
            query = query.where(str_reports.c.status == status)
        with self._engine.connect() as conn:
            return conn.execute(query).scalar() or 0
