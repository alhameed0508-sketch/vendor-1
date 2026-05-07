"""
LDAP/Active Directory authentication client.
Only active when LDAP_ENABLED=true.
"""

import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

# AD group to MuleCatch role mapping
_GROUP_ROLE_MAP = {
    "CN=MuleCatch-Admins": "ADMIN",
    "CN=MuleCatch-Supervisors": "SUPERVISOR",
    "CN=MuleCatch-Investigators": "INVESTIGATOR",
    "CN=MuleCatch-ReadOnly": "READONLY",
    # Common AD patterns
    "CN=Fraud-Admins": "ADMIN",
    "CN=Fraud-Investigators": "INVESTIGATOR",
}


def authenticate_ldap(
    username: str,
    password: str,
    ldap_url: str,
    bind_dn: str,
    bind_password: str,
    search_base: str,
) -> Optional[dict]:
    """
    Authenticate user against LDAP/AD.
    Returns user info dict on success, None on failure.
    """
    try:
        from ldap3 import Server, Connection, ALL, SUBTREE
    except ImportError:
        logger.error("ldap3 package not installed. LDAP authentication unavailable.")
        return None

    try:
        server = Server(ldap_url, get_info=ALL, connect_timeout=5)

        # Bind with service account to search for user
        admin_conn = Connection(
            server, user=bind_dn, password=bind_password, auto_bind=True
        )

        # Search for user
        search_filter = f"(sAMAccountName={username})"
        admin_conn.search(
            search_base,
            search_filter,
            search_scope=SUBTREE,
            attributes=["cn", "memberOf", "mail", "department"],
        )

        if not admin_conn.entries:
            logger.info("LDAP: user '%s' not found", username)
            admin_conn.unbind()
            return None

        user_entry = admin_conn.entries[0]
        user_dn = user_entry.entry_dn
        admin_conn.unbind()

        # Attempt to bind as the user (validates password)
        user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        user_conn.unbind()

        # Extract groups
        groups = (
            [str(g) for g in user_entry.memberOf.values]
            if hasattr(user_entry, "memberOf") and user_entry.memberOf
            else []
        )

        role = map_ldap_groups_to_role(groups)
        display_name = str(user_entry.cn) if hasattr(user_entry, "cn") else username
        department = (
            str(user_entry.department)
            if hasattr(user_entry, "department") and user_entry.department
            else ""
        )

        return {
            "username": username,
            "display_name": display_name,
            "role": role,
            "branch": department,
            "groups": groups,
        }

    except Exception as exc:
        logger.warning("LDAP authentication failed for '%s': %s", username, exc)
        return None


def map_ldap_groups_to_role(groups: List[str]) -> str:
    """Map AD groups to MuleCatch RBAC role. Highest privilege wins."""
    role_priority = ["ADMIN", "SUPERVISOR", "INVESTIGATOR", "READONLY"]

    matched_roles = set()
    for group in groups:
        for pattern, role in _GROUP_ROLE_MAP.items():
            if pattern in group:
                matched_roles.add(role)

    # Return highest-privilege role found
    for role in role_priority:
        if role in matched_roles:
            return role

    return "READONLY"
