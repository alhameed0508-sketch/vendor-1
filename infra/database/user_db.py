"""
SQLite-backed user store for MuleCatch authentication.
Tables: users, failed_logins.
Seeds demo users when ENV != production.
"""

import sqlite3
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

import bcrypt

logger = logging.getLogger(__name__)

_DB_PATH = Path(os.getenv("USER_DB_PATH", "/app/data/users.db"))


def _get_connection() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class UserDB:
    """SQLite user store with bcrypt password hashing."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            global _DB_PATH
            _DB_PATH = Path(db_path)
        self._conn = _get_connection()
        self._init_tables()

    def _init_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'READONLY',
                display_name TEXT NOT NULL DEFAULT '',
                branch TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_login TEXT
            );

            CREATE TABLE IF NOT EXISTS failed_logins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                attempt_time TEXT NOT NULL DEFAULT (datetime('now')),
                ip_address TEXT NOT NULL DEFAULT 'unknown'
            );

            CREATE INDEX IF NOT EXISTS idx_failed_logins_username
                ON failed_logins(username, attempt_time);
        """)
        self._conn.commit()

    def seed_demo_users(self) -> None:
        """Seed default users for development/demo environments."""
        demo_users = [
            (
                "investigator",
                "iob@2024",
                "INVESTIGATOR",
                "Fraud Investigator",
                "Chennai HO",
            ),
            (
                "supervisor",
                "supervisor@2024",
                "SUPERVISOR",
                "Investigation Supervisor",
                "Chennai HO",
            ),
            ("admin", "admin@2024", "ADMIN", "System Administrator", "HO IT"),
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
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO users (username, password_hash, role, display_name, branch, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (username, password_hash, role, display_name, branch, now, now),
        )
        self._conn.commit()
        return self.find_by_username(username)

    def find_by_username(self, username: str) -> Optional[Dict]:
        row = self._conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None

    def update_user(self, username: str, **kwargs) -> Optional[Dict]:
        allowed = {"role", "display_name", "branch", "is_active", "last_login"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.find_by_username(username)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [username]
        self._conn.execute(f"UPDATE users SET {set_clause} WHERE username = ?", values)
        self._conn.commit()
        return self.find_by_username(username)

    def list_users(self) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT id, username, role, display_name, branch, is_active, created_at, last_login FROM users"
        ).fetchall()
        return [dict(r) for r in rows]

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # ── Failed login tracking ─────────────────────────────────────────────────

    def record_failed_login(self, username: str, ip_address: str = "unknown") -> None:
        self._conn.execute(
            "INSERT INTO failed_logins (username, ip_address) VALUES (?, ?)",
            (username, ip_address),
        )
        self._conn.commit()

    def get_failed_login_count(self, username: str, window_minutes: int = 30) -> int:
        row = self._conn.execute(
            """
            SELECT COUNT(*) as cnt FROM failed_logins
            WHERE username = ? AND attempt_time > datetime('now', ?)
            """,
            (username, f"-{window_minutes} minutes"),
        ).fetchone()
        return row["cnt"] if row else 0

    def clear_failed_logins(self, username: str) -> None:
        self._conn.execute("DELETE FROM failed_logins WHERE username = ?", (username,))
        self._conn.commit()

    def close(self):
        self._conn.close()
