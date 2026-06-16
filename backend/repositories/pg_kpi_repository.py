"""
PostgreSQL-backed KPI repository.
Same interface as the in-memory KPIRepository.
Uses the latest kpi_snapshots row as the current state.
"""

import logging
from typing import Dict

from sqlalchemy import text
from sqlalchemy.engine import Engine
from infra.database.postgres import kpi_snapshots

logger = logging.getLogger(__name__)

_DEFAULT_KPI = {
    "total_alerts": 0,
    "false_positives_avoided": 0,
    "hours_saved": 0.0,
    "fraud_prevented_inr": 0.0,
    "investigation_time_reduction_pct": 75,
    "strs_filed": 0,
}


class PgKPIRepository:
    """Data access for KPI metrics backed by PostgreSQL."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def get(self) -> Dict:
        """Return current KPI snapshot (latest row)."""
        with self._engine.connect() as conn:
            row = conn.execute(
                kpi_snapshots.select()
                .order_by(kpi_snapshots.c.id.desc())
                .limit(1)
            ).first()
        if row is None:
            return dict(_DEFAULT_KPI)
        d = dict(row._mapping)
        d.pop("id", None)
        d.pop("snapshot_at", None)
        return d

    def update(self, **kwargs) -> None:
        """Update the latest KPI snapshot row with new values."""
        with self._engine.connect() as conn:
            row = conn.execute(
                kpi_snapshots.select()
                .order_by(kpi_snapshots.c.id.desc())
                .limit(1)
            ).first()

            if row is None:
                # No rows yet — insert one with given values
                values = {**_DEFAULT_KPI, **kwargs}
                conn.execute(kpi_snapshots.insert().values(**values))
            else:
                row_id = row._mapping["id"]
                conn.execute(
                    kpi_snapshots.update()
                    .where(kpi_snapshots.c.id == row_id)
                    .values(**kwargs)
                )
            conn.commit()

    def increment(self, key: str, amount: float = 1) -> None:
        """Increment a KPI counter atomically."""
        with self._engine.connect() as conn:
            row = conn.execute(
                kpi_snapshots.select()
                .order_by(kpi_snapshots.c.id.desc())
                .limit(1)
            ).first()

            if row is None:
                values = dict(_DEFAULT_KPI)
                values[key] = amount
                conn.execute(kpi_snapshots.insert().values(**values))
            else:
                row_id = row._mapping["id"]
                current = row._mapping.get(key, 0) or 0
                conn.execute(
                    kpi_snapshots.update()
                    .where(kpi_snapshots.c.id == row_id)
                    .values(**{key: current + amount})
                )
            conn.commit()
