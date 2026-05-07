"""
Escalation request schemas.
"""

from pydantic import BaseModel, Field


class EscalationRequest(BaseModel):
    alert_id: str = Field(..., min_length=1, max_length=100)
    reason: str = Field(..., min_length=1, max_length=2000)
    priority: str = Field("HIGH", pattern="^(HIGH|CRITICAL|URGENT)$")


class EscalationActionRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|REJECT|REASSIGN)$")
    notes: str = Field("", max_length=2000)
