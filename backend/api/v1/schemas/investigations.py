"""
Investigation request schemas.
"""

from typing import Optional

from pydantic import BaseModel, Field


class OpenInvestigationRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=20)
    source_id: str = Field(..., min_length=1, max_length=100)


class TransitionRequest(BaseModel):
    to: str = Field(..., min_length=1, max_length=20)
    outcome: Optional[str] = Field(None, max_length=20)
    note: str = Field("", max_length=2000)


class AssignRequest(BaseModel):
    assignee: str = Field(..., min_length=1, max_length=100)


class InterventionRequest(BaseModel):
    kind: str = Field(..., min_length=1, max_length=20)
    account_id: str = Field(..., min_length=1, max_length=100)
