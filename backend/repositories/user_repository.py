"""
User repository — data access layer for user operations.
Wraps UserDB with business-level operations.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from infra.database.user_db import UserDB


class UserRepository:
    """User data access with lockout checks."""

    def __init__(
        self,
        user_db: UserDB,
        lockout_max_attempts: int = 5,
        lockout_duration_minutes: int = 30,
    ):
        self._db = user_db
        self._lockout_max_attempts = lockout_max_attempts
        self._lockout_duration_minutes = lockout_duration_minutes

    def find_by_username(self, username: str) -> Optional[Dict]:
        return self._db.find_by_username(username)

    def create_user(
        self,
        username: str,
        password: str,
        role: str = "READONLY",
        display_name: str = "",
        branch: str = "",
    ) -> Dict:
        return self._db.create_user(
            username=username,
            password=password,
            role=role,
            display_name=display_name,
            branch=branch,
        )

    def update_user(self, username: str, **kwargs) -> Optional[Dict]:
        return self._db.update_user(username, **kwargs)

    def list_users(self) -> List[Dict]:
        return self._db.list_users()

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self._db.verify_password(plain_password, hashed_password)

    def record_login_success(self, username: str) -> None:
        self._db.clear_failed_logins(username)
        self._db.update_user(username, last_login=datetime.now(timezone.utc).isoformat())

    def record_failed_login(self, username: str, ip_address: str = "unknown") -> None:
        self._db.record_failed_login(username, ip_address)

    def check_account_lockout(self, username: str) -> bool:
        """Returns True if the account is currently locked out."""
        count = self._db.get_failed_login_count(username, self._lockout_duration_minutes)
        return count >= self._lockout_max_attempts

    def clear_failed_logins(self, username: str) -> None:
        self._db.clear_failed_logins(username)
