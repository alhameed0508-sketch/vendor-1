"""Access records: who works where, and the scope a case sits in. All frozen."""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Institution:
    institution_id: str
    name: str
    kind: str  # PUBLIC | PRIVATE


@dataclass(frozen=True)
class Office:
    office_id: str
    institution_id: str
    parent_id: Optional[str]
    level: str  # HEAD | REGION | BRANCH


@dataclass(frozen=True)
class Employee:
    user_id: str
    institution_id: str
    office_id: str
    role: str


@dataclass(frozen=True)
class UserContext:
    user_id: str
    role: str
    institution_id: Optional[str]
    office_id: Optional[str]


@dataclass(frozen=True)
class CaseScope:
    institution_id: Optional[str]
    office_id: Optional[str]
    office_path: Tuple[str, ...]  # the case's office, then its parents up to the head office
    assignee: Optional[str]


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
