"""
Feedback request schemas.
"""

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    alert_id: str = Field(..., min_length=1, max_length=100)
    is_true_positive: bool
    investigator_id: str = Field("investigator_001", max_length=100)
    notes: str = Field("", max_length=5000)
