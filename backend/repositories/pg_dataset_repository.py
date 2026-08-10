"""
PostgreSQL-backed dataset repository.
Same interface as DatasetRepository. Stores the currently active uploaded
(or generated) dataset as a single JSONB row — set() replaces it wholesale.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.engine import Engine

from backend.infra.database.postgres import uploaded_datasets

logger = logging.getLogger(__name__)


class PgDatasetRepository:
    """PostgreSQL data access for the active detection dataset."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def get(self) -> Optional[Dict]:
        with self._engine.connect() as conn:
            row = conn.execute(uploaded_datasets.select().order_by(uploaded_datasets.c.id.desc()).limit(1)).first()
        return dict(row._mapping["payload"]) if row else None

    def set(self, dataset: Dict) -> None:
        """Replace the active dataset with the given one."""
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(uploaded_datasets.delete())
            conn.execute(uploaded_datasets.insert().values(payload=dataset, uploaded_at=now))

    def clear(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(uploaded_datasets.delete())
