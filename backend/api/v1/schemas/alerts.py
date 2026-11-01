"""
Alert request schemas.
"""

from typing import Optional

from pydantic import BaseModel, Field


class AlertUpdateRequest(BaseModel):
    status: Optional[str] = Field(None, pattern="^(OPEN|UNDER_REVIEW|RESOLVED|FALSE_POSITIVE|STR_FILED)$")
    investigator_notes: Optional[str] = Field(None, max_length=5000)
