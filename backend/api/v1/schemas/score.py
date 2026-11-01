"""Per-payment scoring request schema."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ScorePaymentRequest(BaseModel):
    txn_id: str = Field(..., min_length=1, max_length=100)
    from_account: str = Field(..., min_length=1, max_length=100)
    to_account: str = Field(..., min_length=1, max_length=100)
    amount: float = Field(..., gt=0, le=1e10)
    timestamp: str = Field(..., min_length=1, max_length=40)
    device_id: str = Field("", max_length=100)
    ip_address: str = Field("", max_length=64)
    upi_id: str = Field("", max_length=100)

    @field_validator("timestamp")
    @classmethod
    def _iso_timestamp(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("timestamp must be ISO-8601") from exc
        return value
