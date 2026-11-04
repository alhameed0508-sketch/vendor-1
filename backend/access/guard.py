"""Applies the access policy to investigations.

A case the caller may not read is reported as "not found", so the response never confirms
that another institution's case exists. A case they may read but not change gets a 403.
"""

from typing import Dict, List, Optional

from access.directory import AccessDirectory
from access.models import CaseScope, UserContext
from access.policy import can, can_open
from core.exceptions import AuthorizationError, NotFoundError

TRANSITION_ACTIONS = {"ESCALATED": "escalate", "CLOSED": "close"}


def action_for_transition(to: str) -> str:
    return TRANSITION_ACTIONS.get(to, "write")


class AccessGuard:
    def __init__(self, directory: AccessDirectory):
        self._directory = directory

    def context(self, user: dict) -> Optional[UserContext]:
        return self._directory.context_for(user)

    def scope_of(self, investigation: Dict) -> CaseScope:
        return self._directory.scope_for(
            investigation.get("institution_id"), investigation.get("office_id"), investigation.get("assignee")
        )

    def opener(self, user: dict) -> UserContext:
        ctx = self.context(user)
        if ctx is None:
            raise AuthorizationError("This account is not set up for case work")
        decision = can_open(ctx)
        if not decision.allowed:
            raise AuthorizationError(decision.reason)
        return ctx

    def require(self, user: dict, action: str, investigation: Dict) -> None:
        ctx, scope = self.context(user), self.scope_of(investigation)
        if ctx is None or not can(ctx, "read", scope).allowed:
            raise NotFoundError("Investigation", investigation["investigation_id"])
        decision = can(ctx, action, scope)
        if not decision.allowed:
            raise AuthorizationError(decision.reason)

    def visible(self, user: dict, investigations: List[Dict]) -> List[Dict]:
        ctx = self.context(user)
        if ctx is None:
            return []
        return [i for i in investigations if can(ctx, "read", self.scope_of(i)).allowed]
