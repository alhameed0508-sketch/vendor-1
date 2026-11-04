"""
PostgreSQL-backed user store for MuleCatch authentication.
Same interface as the SQLite UserDB.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import bcrypt
from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine

from backend.infra.database.postgres import failed_logins_table, users_table

logger = logging.getLogger(__name__)


def _row_to_dict(row) -> Dict:
    d = dict(row._mapping)
    for key in ("created_at", "updated_at", "last_login"):
        if d.get(key) is not None:
            d[key] = d[key].isoformat()
    # Convert boolean is_active to int for SQLite compatibility
    if "is_active" in d:
        d["is_active"] = 1 if d["is_active"] else 0
    return d


class PgUserDB:
    """PostgreSQL user store with bcrypt password hashing."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def seed_demo_users(self) -> None:
        """Seed default users for development/demo environments."""
        import os

        demo_users = [
            (
                "investigator",
                os.getenv("DEMO_INVESTIGATOR_PASSWORD", "iob@2024"),
                "INVESTIGATOR",
                "Fraud Investigator",
                "Chennai HO",
            ),
            (
                "supervisor",
                os.getenv("DEMO_SUPERVISOR_PASSWORD", "supervisor@2024"),
                "SUPERVISOR",
                "Investigation Supervisor",
                "Chennai HO",
            ),
            (
                "admin",
                os.getenv("DEMO_ADMIN_PASSWORD", "admin@2024"),
                "ADMIN",
                "System Administrator",
                "HO IT",
            ),
        ]
        for username, password, role, display_name, branch in demo_users:
            existing = self.find_by_username(username)
            if not existing:
                self.create_user(
                    username=username,
                    password=password,
                    role=role,
                    display_name=display_name,
                    branch=branch,
                )
        logger.info("Demo users seeded (%d users)", len(demo_users))

    def create_user(
        self,
        username: str,
        password: str,
        role: str = "READONLY",
        display_name: str = "",
        branch: str = "",
    ) -> Dict:
        password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        now = datetime.now(timezone.utc)
        with self._engine.connect() as conn:
            conn.execute(
                users_table.insert().values(
                    username=username,
                    password_hash=password_hash,
                    role=role,
                    display_name=display_name,
                    branch=branch,
                    created_at=now,
                    updated_at=now,
                )
            )
            conn.commit()
        return self.find_by_username(username)

    def find_by_username(self, username: str) -> Optional[Dict]:
        with self._engine.connect() as conn:
            row = conn.execute(users_table.select().where(users_table.c.username == username)).first()
        return _row_to_dict(row) if row else None

    def update_user(self, username: str, **kwargs) -> Optional[Dict]:
        allowed = {"role", "display_name", "branch", "is_active", "last_login"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.find_by_username(username)
        updates["updated_at"] = datetime.now(timezone.utc)
        with self._engine.connect() as conn:
            conn.execute(users_table.update().where(users_table.c.username == username).values(**updates))
            conn.commit()
        return self.find_by_username(username)

    def list_users(self) -> List[Dict]:
        cols = [
            users_table.c.id,
            users_table.c.username,
            users_table.c.role,
            users_table.c.display_name,
            users_table.c.branch,
            users_table.c.is_active,
            users_table.c.created_at,
            users_table.c.last_login,
        ]
        with self._engine.connect() as conn:
            rows = conn.execute(select(*cols)).fetchall()
        return [_row_to_dict(r) for r in rows]

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # ── Failed login tracking ─────────────────────────────────────────────────

    def record_failed_login(self, username: str, ip_address: str = "unknown") -> None:
        now = datetime.now(timezone.utc)
        with self._engine.connect() as conn:
            conn.execute(
                failed_logins_table.insert().values(
                    username=username,
                    attempt_time=now,
                    ip_address=ip_address,
                )
            )
            conn.commit()

    def get_failed_login_count(self, username: str, window_minutes: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        with self._engine.connect() as conn:
            count = conn.execute(
                select(func.count())
                .select_from(failed_logins_table)
                .where(failed_logins_table.c.username == username)
                .where(failed_logins_table.c.attempt_time > cutoff)
            ).scalar()
        return count or 0

    def clear_failed_logins(self, username: str) -> None:
        with self._engine.connect() as conn:
            conn.execute(delete(failed_logins_table).where(failed_logins_table.c.username == username))
            conn.commit()

    def close(self):
        """No-op — engine lifecycle managed externally."""
        pass
