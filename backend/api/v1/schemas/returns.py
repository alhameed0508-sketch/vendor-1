"""
Return-claim request schemas.
"""

import base64
import binascii
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

MAX_FILE_BYTES = 4_000_000


def _decode(value: Optional[str]) -> Optional[bytes]:
    if value is None:
        return None
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("File must be base64 encoded") from exc
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("File is too large; the limit is 4 MB")
    return raw


class History(BaseModel):
    orders_90d: int = Field(0, ge=0, le=10000)
    returns_90d: int = Field(0, ge=0, le=10000)
    account_age_days: int = Field(365, ge=0, le=36500)


class ReturnClaimRequest(BaseModel):
    customer_id: str = Field(..., min_length=1, max_length=64)
    customer_name: str = Field(..., min_length=1, max_length=120)
    item: str = Field(..., min_length=1, max_length=160)
    category: Literal["electronics", "apparel", "home", "beauty", "other"] = "other"
    amount: int = Field(..., gt=0, le=100_000_000)
    reason_text: str = Field(..., min_length=1, max_length=1000)
    delivered_at: datetime
    returned_at: datetime
    device_id: str = Field("", max_length=64)
    address: str = Field("", max_length=200)
    payment_fp: str = Field("", max_length=64)
    expected_device: str = Field("", max_length=64)
    delivery_geo: Optional[List[float]] = Field(None, min_length=2, max_length=2)
    event_date: Optional[str] = Field(None, max_length=10)
    photo_labels: List[str] = Field(default_factory=list, max_length=20)
    receipt_amount: Optional[int] = Field(None, ge=0)
    history: Optional[History] = None
    photo_b64: Optional[str] = None
    receipt_pdf_b64: Optional[str] = None

    @field_validator("photo_b64", "receipt_pdf_b64")
    @classmethod
    def _valid_file(cls, value):
        _decode(value)
        return value

    def photo_bytes(self) -> Optional[bytes]:
        return _decode(self.photo_b64)

    def receipt_bytes(self) -> Optional[bytes]:
        return _decode(self.receipt_pdf_b64)


class ReviewRequest(BaseModel):
    outcome: Literal["refund", "request_proof", "reject", "escalate"]
    notes: str = Field("", max_length=1000)


class CarrierEvent(BaseModel):
    claim_id: str = Field(..., max_length=32)
    event: Literal["delivered", "in_transit", "lost_in_transit", "damaged_in_transit", "returned_to_sender"]
    occurred_at: datetime
    carrier: str = Field("", max_length=60)
    tracking_id: str = Field("", max_length=60)


class ChargebackEvent(BaseModel):
    claim_id: str = Field(..., max_length=32)
    chargeback_id: str = Field(..., min_length=1, max_length=40)
    status: Literal["opened", "won", "lost"]
    reason_code: str = Field("", max_length=20)
    amount: int = Field(..., gt=0)
    occurred_at: datetime
