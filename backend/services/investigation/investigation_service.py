"""
Investigation workflow — one status path over alert cases and complaint cases.

The service keeps the workflow state (status, assignee, outcome, history) and points at the source
case by id. It never edits the alert or complaint itself. The outcome is a person's decision;
nothing here derives it from a model score. Every move is written to the audit hash chain.
"""

import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from core.exceptions import ConflictError, NotFoundError, ValidationError
from services.audit_service import AuditService

NEW, UNDER_REVIEW, INVESTIGATING, ESCALATED, RESOLVED, CLOSED = (
    "NEW",
    "UNDER_REVIEW",
    "INVESTIGATING",
    "ESCALATED",
    "RESOLVED",
    "CLOSED",
)
TRANSITIONS = {
    NEW: {UNDER_REVIEW},
    UNDER_REVIEW: {INVESTIGATING},
    INVESTIGATING: {ESCALATED, RESOLVED},
    ESCALATED: {INVESTIGATING, RESOLVED},
    RESOLVED: {CLOSED, INVESTIGATING},
    CLOSED: set(),
}
OUTCOMES = ("CONFIRMED", "FALSE_POSITIVE", "UNRESOLVED")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _present(investigation: Dict) -> Dict:
    """The stored record plus the statuses it may move to, so clients need not copy the rules."""
    return {**investigation, "allowed_next": sorted(TRANSITIONS[investigation["status"]])}


def _entry(to: str, by: str, note: str) -> Dict:
    return {"to": to, "by": by, "note": note, "at": _now()}


class InvestigationService:
    """Open, assign, move and read investigations."""

    def __init__(self, repo, audit: AuditService, resolvers: Dict[str, Callable[[str], bool]]):
        self._repo = repo
        self._audit = audit
        self._resolvers = resolvers

    def open(
        self,
        source: str,
        source_id: str,
        user: str,
        institution_id: Optional[str] = None,
        office_id: Optional[str] = None,
        assignee: Optional[str] = None,
    ) -> Dict:
        resolver = self._resolvers.get(source)
        if resolver is None:
            raise ValidationError(f"Unknown case source '{source}'. Use one of: {', '.join(sorted(self._resolvers))}")
        if not resolver(source_id):
            raise NotFoundError(f"{source.capitalize()} case", source_id)
        if self._repo.find_by_source(source, source_id, institution_id):
            raise ConflictError(f"An investigation is already open for {source} {source_id}")
        investigation = {
            "investigation_id": f"INV_{uuid.uuid4().hex[:8].upper()}",
            "source": source,
            "source_id": source_id,
            "status": NEW,
            "institution_id": institution_id,
            "office_id": office_id,
            "assignee": assignee,
            "outcome": None,
            "opened_at": _now(),
            "history": [_entry(NEW, user, "")],
        }
        stored = self._repo.create(investigation)
        self._audit.log("INVESTIGATION_OPENED", user, source_id, f"investigation={stored['investigation_id']}")
        return _present(stored)

    def get(self, investigation_id: str) -> Dict:
        found = self._repo.find_by_id(investigation_id)
        if not found:
            raise NotFoundError("Investigation", investigation_id)
        return _present(found)

    def list_all(self) -> List[Dict]:
        return [_present(i) for i in self._repo.find_all()]

    def assign(self, investigation_id: str, assignee: str, user: str) -> Dict:
        current = self.get(investigation_id)
        if current["status"] == CLOSED:
            raise ConflictError("A closed investigation cannot be reassigned")
        updated = self._repo.update(investigation_id, assignee=assignee)
        self._audit.log("INVESTIGATION_ASSIGNED", user, current["source_id"], f"assignee={assignee}")
        return _present(updated)

    def transition(
        self,
        investigation_id: str,
        to: str,
        user: str,
        outcome: Optional[str] = None,
        note: str = "",
    ) -> Dict:
        current = self.get(investigation_id)
        if to not in TRANSITIONS:
            raise ValidationError(f"Unknown status '{to}'")
        if to not in TRANSITIONS[current["status"]]:
            raise ConflictError(f"Cannot move from {current['status']} to {to}")
        if to == RESOLVED and outcome not in OUTCOMES:
            raise ValidationError(f"Resolving needs an outcome: {', '.join(OUTCOMES)}")
        updates = {
            "status": to,
            "history": [*current["history"], _entry(to, user, note)],
            **({"outcome": outcome} if to == RESOLVED else {}),
        }
        updated = self._repo.update(investigation_id, **updates)
        detail = f"from={current['status']}" + (f" outcome={outcome}" if to == RESOLVED else "")
        self._audit.log(f"INVESTIGATION_{to}", user, current["source_id"], detail)
        return _present(updated)
