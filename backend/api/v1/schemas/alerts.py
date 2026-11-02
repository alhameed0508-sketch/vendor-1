"""
Alert request schemas.
"""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

# Closing an alert needs a written reason so the decision can be audited later.
REASON_REQUIRED_STATUSES = ("NO_FURTHER_ACTION", "SUSPICION_CONFIRMED_ESCALATED")


class AlertUpdateRequest(BaseModel):
    status: Optional[str] = Field(
        None,
        pattern="^(OPEN|UNDER_REVIEW|RESOLVED|FALSE_POSITIVE|STR_FILED|NO_FURTHER_ACTION|SUSPICION_CONFIRMED_ESCALATED)$",
    )
    investigator_notes: Optional[str] = Field(None, max_length=5000)

    @model_validator(mode="after")
    def _disposition_needs_reason(self):
        if self.status in REASON_REQUIRED_STATUSES and not (self.investigator_notes or "").strip():
            raise ValueError(f"{self.status} requires investigator_notes giving the reason")
        return self
