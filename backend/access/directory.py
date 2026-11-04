"""In-memory directory of institutions, offices and employees.

A Postgres version would sit behind the same methods; adding those tables is a schema change
and waits for the owner's approval.
"""

from typing import Dict, Iterable, Optional, Tuple

from access.models import CaseScope, Employee, Institution, Office, UserContext


class AccessDirectory:
    def __init__(self, institutions: Iterable[Institution], offices: Iterable[Office], employees: Iterable[Employee]):
        self.institutions: Tuple[Institution, ...] = tuple(institutions)
        self._offices: Dict[str, Office] = {o.office_id: o for o in offices}
        self._employees: Dict[str, Employee] = {e.user_id: e for e in employees}

    def office_path(self, office_id: Optional[str]) -> Tuple[str, ...]:
        path = []
        current = self._offices.get(office_id)
        while current is not None and current.office_id not in path:
            path.append(current.office_id)
            current = self._offices.get(current.parent_id)
        return tuple(path)

    def context_for(self, user: dict) -> Optional[UserContext]:
        """Who the caller is at work. The role is the one in the token, the place is the directory's."""
        user_id, role = user.get("sub", ""), user.get("role", "")
        if role == "ADMIN":
            return UserContext(user_id, role, None, None)
        employee = self._employees.get(user_id)
        if employee is None:
            return None
        return UserContext(user_id, role, employee.institution_id, employee.office_id)

    def scope_for(self, institution_id: Optional[str], office_id: Optional[str], assignee: Optional[str]) -> CaseScope:
        return CaseScope(institution_id, office_id, self.office_path(office_id), assignee)
