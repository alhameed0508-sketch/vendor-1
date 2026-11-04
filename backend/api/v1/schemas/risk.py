"""Request schemas for the unified risk engine (/api/v1/risk)."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


def _iso(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("must be an ISO-8601 timestamp") from exc
    return value


class AuthEvent(BaseModel):
    type: str = Field(..., min_length=1, max_length=40)
    at: str = Field(..., min_length=1, max_length=40)

    _check_at = field_validator("at")(classmethod(lambda cls, v: _iso(v)))


class RiskSession(BaseModel):
    """What the bank's app and login systems know about the session (all optional)."""

    session_id: str = Field("", max_length=100)
    device_id: str = Field("", max_length=100)
    ip: str = Field("", max_length=64)
    city: str = Field("", max_length=60)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    auth_events: List[AuthEvent] = Field(default_factory=list, max_length=20)
    typing_ms_per_char: Optional[float] = Field(None, gt=0, le=5000)
    remote_access: bool = False
    device_flags: List[str] = Field(default_factory=list, max_length=10)


class RiskContext(BaseModel):
    """Payment context from the app: channel, payee age, call state, note."""

    channel: str = Field("UPI_PUSH", max_length=20)
    beneficiary_added_at: Optional[str] = Field(None, max_length=40)
    on_call: bool = False
    note: str = Field("", max_length=200)
    app_switch_count: int = Field(0, ge=0, le=1000)
    amount_pasted: bool = False
    backspace_count: int = Field(0, ge=0, le=10000)
    payee_name: str = Field("", max_length=120)

    _check_added = field_validator("beneficiary_added_at")(classmethod(lambda cls, v: _iso(v)))


class RiskEventRequest(BaseModel):
    txn_id: str = Field(..., min_length=1, max_length=100)
    from_account: str = Field(..., min_length=1, max_length=100)
    to_account: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0, le=1e10)
    timestamp: str = Field(..., min_length=1, max_length=40)
    session: Optional[RiskSession] = None
    context: Optional[RiskContext] = None

    _check_ts = field_validator("timestamp")(classmethod(lambda cls, v: _iso(v)))

    def to_event(self) -> dict:
        data = self.model_dump()
        if data["session"] is None:
            data.pop("session")
        if data["context"] is None:
            data["context"] = {"channel": "UPI_PUSH"}
        return data


class RiskFeedbackRequest(BaseModel):
    outcome: Literal["CONFIRMED_FRAUD", "FALSE_ALERT"]
    note: str = Field("", max_length=500)
