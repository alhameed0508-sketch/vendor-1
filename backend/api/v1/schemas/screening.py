"""
Screening request/response schemas.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ScreenAccountRequest(BaseModel):
    account_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    identifiers: Optional[List[str]] = None


class BatchScreenRequest(BaseModel):
    accounts: List[ScreenAccountRequest] = Field(..., min_length=1, max_length=100)


class WatchlistImportRequest(BaseModel):
    source: str = Field("CUSTOM", min_length=1, max_length=50)
