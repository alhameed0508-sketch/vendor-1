"""
Shared response envelope schema.
"""

from typing import Any, Optional

from pydantic import BaseModel


class APIResponse(BaseModel):
    """Standard API response envelope."""

    success: bool
    data: Optional[Any] = None
    error: Optional[Any] = None
    timestamp: str
