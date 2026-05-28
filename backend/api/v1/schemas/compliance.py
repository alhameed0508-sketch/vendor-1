"""
Compliance request schemas.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class STRExportRequest(BaseModel):
    alert_ids: List[str] = Field(..., min_length=1, max_length=50)


class STRCreateRequest(BaseModel):
    """Create a new Suspicious Transaction Report."""
    alert_ids: List[str] = Field(..., min_length=1, max_length=50)
    account_ids: List[str] = Field(default_factory=list, max_length=100)
    narrative: str = Field(..., min_length=10, max_length=10000)
    reporting_entity: str = Field("Indian Overseas Bank", max_length=200)


class STRApproveRequest(BaseModel):
    """Supervisor approval for STR submission."""
    approved_by: str = Field(..., min_length=1, max_length=100)
