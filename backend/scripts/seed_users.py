"""
CLI script to create initial admin user for production deployment.
Usage: python -m scripts.seed_users
"""

import os
import sys
import getpass

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_project_dir = os.path.dirname(_backend_dir)
sys.path.insert(0, _backend_dir)
sys.path.insert(0, _project_dir)

from infra.database.user_db import UserDB  # noqa: E402


def main():
    print("=" * 50)
    print("MuleCatch — Create Admin User")
    print("=" * 50)

    db = UserDB()

    username = os.getenv("ADMIN_USERNAME") or input("Username: ").strip()
    if not username:
        print("Error: username cannot be empty")
        sys.exit(1)

    existing = db.find_by_username(username)
    if existing:
        print(f"User '{username}' already exists (role: {existing['role']})")
        sys.exit(0)

    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    if len(password) < 8:
        print("Error: password must be at least 8 characters")
        sys.exit(1)

    display_name = (
        os.getenv("ADMIN_DISPLAY_NAME")
        or input("Display name [Admin]: ").strip()
        or "Admin"
    )
    branch = os.getenv("ADMIN_BRANCH") or input("Branch [HO IT]: ").strip() or "HO IT"

    user = db.create_user(
        username=username,
        password=password,
        role="ADMIN",
        display_name=display_name,
        branch=branch,
    )

    print(f"\nAdmin user created: {user['username']} (role: {user['role']})")
    db.close()


if __name__ == "__main__":
    main()
