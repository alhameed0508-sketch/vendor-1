"""
Compliance request schemas.
"""

from typing import List

from pydantic import BaseModel, Field


class STRExportRequest(BaseModel):
    alert_ids: List[str] = Field(..., min_length=1, max_length=50)
