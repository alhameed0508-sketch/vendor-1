"""Domain models. Plain Pydantic, no database or network imports."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_serializer, field_validator, model_validator

from intentlock.money import CURRENCY_EXPONENT

RequirementValue = StrictInt | StrictBool | StrictStr


def canonical_json(data) -> str:
    """Stable JSON for hashing: sorted keys, no spaces, UTF-8. Callers must not pass floats."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Condition(str, Enum):
    NEW = "new"
    USED = "used"
    REFURBISHED = "refurbished"


class Decision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REAUTHORISE = "REAUTHORISE"
    REVIEW = "REVIEW"


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── mandate ──────────────────────────────────────────────────────────────────
class ProductSpec(_Strict):
    category: str = Field(min_length=1, max_length=60)
    condition: Condition
    quantity: int = Field(ge=1, le=99)
    model: str | None = Field(default=None, max_length=120)
    requirements: dict[str, RequirementValue] = Field(default_factory=dict)

    @field_validator("category")
    @classmethod
    def _norm_category(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("model")
    @classmethod
    def _norm_model(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None

    @field_validator("requirements")
    @classmethod
    def _norm_requirements(cls, v: dict) -> dict:
        out = {}
        for key, value in v.items():
            k = key.strip().lower()
            if not k or len(k) > 60 or not all(c.isalnum() or c == "_" for c in k):
                raise ValueError(f"Invalid requirement name: {key!r}")
            out[k] = value
        return out


class SellerPolicy(_Strict):
    mode: Literal["allowlist", "any"]
    approved_seller_ids: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def _allowlist_needs_sellers(self):
        if self.mode == "allowlist" and not self.approved_seller_ids:
            raise ValueError("An allowlist seller policy needs at least one approved seller")
        return self


class SpendingPolicy(_Strict):
    maximum_total_minor: int = Field(gt=0, le=10**12)
    include_shipping: bool
    include_tax: bool


class SubstitutionPolicy(_Strict):
    allowed: bool
    require_reapproval: bool


class MandateSpec(_Strict):
    """The buyer's structured authorisation for one purchase task. Hashing this gives the mandate hash."""

    currency: str = Field(min_length=3, max_length=3)
    product: ProductSpec
    seller: SellerPolicy
    spending: SpendingPolicy
    substitution: SubstitutionPolicy
    expires_at: datetime

    @field_validator("currency")
    @classmethod
    def _known_currency(cls, v: str) -> str:
        v = v.upper()
        if v not in CURRENCY_EXPONENT:
            raise ValueError(f"Unsupported currency: {v}")
        return v

    @field_validator("expires_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        return v.astimezone(timezone.utc).replace(microsecond=0)

    @field_serializer("expires_at")
    def _ser_expires(self, v: datetime) -> str:
        return v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def canonical(self) -> str:
        return canonical_json(self.model_dump(mode="json"))

    def canonical_hash(self) -> str:
        return sha256_hex(self.canonical())


# ── facts the policy engine reads ────────────────────────────────────────────
class MandateState(BaseModel):
    mandate_id: str
    version: int
    status: str
    is_current_version: bool


class OfferFacts(BaseModel):
    product_id: str
    title: str
    description: str = ""
    category: str
    condition: str
    attributes: dict[str, RequirementValue] = Field(default_factory=dict)
    seller_id: str
    seller_name: str
    merchant_checkout_eligible: bool
    availability_status: str = "in_stock"
    unit_amount_minor: int
    currency: str
    shipping_amount_minor: int | None = None
    tax_amount_minor: int | None = None
    source: str = "demo_catalogue"
    source_reference: str = ""


class QuoteFacts(BaseModel):
    quote_id: str
    product_id: str
    quantity: int
    currency: str
    unit_amount_minor: int
    shipping_amount_minor: int | None
    tax_amount_minor: int | None
    total_amount_minor: int | None
    expires_at: datetime


class OrderItem(BaseModel):
    sku: str | None = None
    quantity: int
    unit_amount_minor: int


class OrderFacts(BaseModel):
    """The payment-side record, as returned by the payment provider after buyer approval."""

    order_id: str
    status: str
    currency: str
    total_minor: int
    payee_merchant_id: str | None = None
    payee_email: str | None = None
    purchase_unit_count: int = 1
    items: list[OrderItem] = Field(default_factory=list)
    custom_id: str | None = None
    has_capture: bool = False


class ExpectedOrder(BaseModel):
    """What the server stored when it created the order."""

    order_id: str
    payee_merchant_id: str | None = None
    payee_email: str | None = None
    custom_id: str
    sku: str


class PolicyCheck(BaseModel):
    rule_id: str
    status: CheckStatus
    on_fail: Decision
    expected: str
    observed: str
    source: str
    reason: str


class Evaluation(BaseModel):
    policy_version: str
    stage: Literal["PRE_ORDER", "PRE_CAPTURE"]
    decision: Decision
    checks: list[PolicyCheck]
    failed_constraints: list[str]
    requires_buyer_reapproval: bool
