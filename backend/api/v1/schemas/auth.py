"""
Auth request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    token: str = Field(..., min_length=1)


class LogoutRequest(BaseModel):
    token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    auth_enabled: bool = True
