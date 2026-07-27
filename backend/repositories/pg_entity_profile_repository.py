"""PostgreSQL identity profile repository."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from backend.infra.database.postgres import identity_profiles


class PgEntityProfileRepository:
    def __init__(self, engine: Engine):
        self._engine = engine

    def find_candidates(self, profile: Dict, limit: int = 200) -> List[Dict]:
        exact = [
            identity_profiles.c[field] == profile[field]
            for field in (
                "phone_hash",
                "email_hash",
                "government_id_hash",
                "device_fingerprint",
            )
            if profile.get(field)
        ]
        query = select(identity_profiles).where(
            identity_profiles.c.entity_id != profile["entity_id"]
        )
        if exact:
            query = query.order_by(or_(*exact).desc())
        query = query.limit(limit)
        with self._engine.connect() as conn:
            rows = conn.execute(query).fetchall()
        return [dict(row._mapping) for row in rows]

    def upsert_profile(self, profile: Dict) -> None:
        values = dict(profile)
        values["updated_at"] = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                insert(identity_profiles)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[identity_profiles.c.entity_id],
                    set_={
                        key: value
                        for key, value in values.items()
                        if key != "entity_id"
                    },
                )
            )
