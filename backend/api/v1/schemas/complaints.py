"""
Fraud complaint request schemas.
"""

import json
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from complaints.evidence import KINDS, SOURCES
from pydantic import BaseModel, Field, field_validator, model_validator

MAX_EVIDENCE_DATA_CHARS = 4000
SYSTEM_ONLY_KINDS = ("mule_match",)  # written by MuleCatch itself, never posted


def _require_timezone(value: Optional[datetime]) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        raise ValueError("Timestamps need a timezone, for example 2027-02-14T21:10:00+05:30")
    return value


class ComplaintCreateRequest(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=120)
    customer_type: Literal["INDIVIDUAL", "SOLE_PROPRIETOR", "COMPANY"] = "INDIVIDUAL"
    account: str = Field(..., min_length=4, max_length=34)
    channel: Literal["UPI", "IMPS", "NEFT", "NETBANKING", "DEBIT_CARD", "CREDIT_CARD", "WALLET"]
    amount: int = Field(..., gt=0, le=1_000_000_000)
    amount_after_report: int = Field(0, ge=0)
    recovered: int = Field(0, ge=0)
    occurred_at: datetime
    reported_at: datetime
    ncrp_reported_at: Optional[datetime] = None
    compensation_form_at: Optional[datetime] = None
    cross_border: bool = False
    beneficiary_account: str = Field("", max_length=64)
    beneficiary_bank: str = Field("", max_length=80)
    description: str = Field("", max_length=2000)
    previously_compensated: bool = False

    _aware = field_validator("occurred_at", "reported_at", "ncrp_reported_at", "compensation_form_at")(
        _require_timezone)

    @model_validator(mode="after")
    def _consistent(self):
        if self.reported_at < self.occurred_at:
            raise ValueError("The customer cannot report a fraud before it happened")
        if self.ncrp_reported_at and self.ncrp_reported_at < self.occurred_at:
            raise ValueError("The NCRP report cannot come before the fraud")
        if self.amount_after_report > self.amount or self.recovered > self.amount:
            raise ValueError("Amounts after report or recovered cannot exceed the disputed amount")
        return self


class EvidenceRequest(BaseModel):
    source: Literal[SOURCES]
    kind: Literal[KINDS]
    at: datetime
    summary: str = Field(..., min_length=1, max_length=500)
    data: Dict[str, Any] = Field(default_factory=dict)

    _aware = field_validator("at")(_require_timezone)

    @model_validator(mode="after")
    def _posted_evidence_only(self):
        if self.kind in SYSTEM_ONLY_KINDS or self.source == "MULECATCH":
            raise ValueError("MuleCatch findings are added by MuleCatch, not posted")
        if len(json.dumps(self.data, default=str)) > MAX_EVIDENCE_DATA_CHARS:
            raise ValueError(f"Evidence data is limited to {MAX_EVIDENCE_DATA_CHARS} characters")
        return self


class DecisionRequest(BaseModel):
    outcome: Literal["ZERO_LIABILITY", "CUSTOMER_LIABLE", "SHARED_LIABILITY", "NOT_FRAUD"]
    customer_liability: int = Field(..., ge=0)
    notes: str = Field(..., min_length=1, max_length=2000)
