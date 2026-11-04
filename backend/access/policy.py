"""Who may do what to a case. A pure function: no I/O, no clock, same inputs give the same answer.

Order of checks: platform administrator, then institution, then office scope, then role.
A supervisor covers their office and every office below it. Anyone else covers their own office only.
Investigators change a case only when it is assigned to them.
"""

from access.models import CaseScope, Decision, UserContext

SUPERVISOR_ACTIONS = frozenset({"read", "write", "escalate", "assign", "close"})
ASSIGNED_ACTIONS = frozenset({"write", "escalate"})
OPENING_ROLES = frozenset({"INVESTIGATOR", "SUPERVISOR", "ADMIN"})


def _deny(reason: str) -> Decision:
    return Decision(False, reason)


def can(user: UserContext, action: str, case: CaseScope) -> Decision:
    if user.role == "ADMIN":
        return Decision(True, "platform administrator")
    if user.institution_id is None or user.institution_id != case.institution_id:
        return _deny("case belongs to another institution")

    if user.role == "SUPERVISOR":
        if user.office_id not in case.office_path:
            return _deny("case is outside this supervisor's offices")
        return (
            Decision(True, "supervisor over this office")
            if action in SUPERVISOR_ACTIONS
            else _deny(f"unknown action '{action}'")
        )

    if user.role not in ("INVESTIGATOR", "READONLY"):
        return _deny(f"role '{user.role}' has no case access")
    if user.office_id != case.office_id:
        return _deny("case is in another office")
    if action == "read":
        return Decision(True, "same office")
    if user.role == "INVESTIGATOR" and action in ASSIGNED_ACTIONS:
        if case.assignee == user.user_id:
            return Decision(True, "assigned to this investigator")
        return _deny("case is not assigned to this investigator")
    return _deny(f"role '{user.role}' may not {action}")


def can_open(user: UserContext) -> Decision:
    if user.role in OPENING_ROLES:
        return Decision(True, "may open cases")
    return _deny(f"role '{user.role}' may not open cases")
