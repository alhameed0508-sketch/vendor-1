"""Payment-provider interface. PayPal is the first adapter; others implement the same four calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol


class ProviderError(Exception):
    """Base class for provider failures."""


class ProviderUnavailable(ProviderError):
    """Timeout, network failure or 5xx. The outcome of the call is unknown: reconcile, do not retry blindly."""


class ProviderRejected(ProviderError):
    """The provider answered and refused the request (4xx)."""

    def __init__(self, status: int, name: str, message: str, issue: str = "", debug_id: str = "") -> None:
        super().__init__(f"{name}: {issue or message}")
        self.status, self.name, self.message, self.issue, self.debug_id = status, name, message, issue, debug_id


@dataclass(frozen=True)
class OrderLine:
    sku: str | None
    quantity: int
    unit_amount_minor: int


@dataclass(frozen=True)
class CaptureInfo:
    capture_id: str
    status: str
    amount_minor: int
    currency: str
    created_at: str | None = None


@dataclass(frozen=True)
class OrderSnapshot:
    """A provider order normalised to the fields IntentLock verifies."""

    order_id: str
    status: str
    currency: str
    total_minor: int
    payee_merchant_id: str | None
    payee_email: str | None
    purchase_unit_count: int
    items: tuple[OrderLine, ...]
    custom_id: str | None
    reference_id: str | None
    captures: tuple[CaptureInfo, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OrderRequest:
    """Everything needed to create an order. Built by the server from the stored quote, never from the browser."""

    reference: str  # checkout session id
    title: str
    sku: str
    quantity: int
    currency: str
    unit_amount_minor: int
    shipping_amount_minor: int
    tax_amount_minor: int
    total_amount_minor: int


class PaymentProvider(Protocol):
    name: str

    def create_order(self, request: OrderRequest, request_id: str) -> OrderSnapshot: ...

    def get_order(self, order_id: str) -> OrderSnapshot: ...

    def capture_order(self, order_id: str, request_id: str) -> OrderSnapshot: ...

    def verify_webhook(self, headers: Mapping[str, str], raw_body: bytes, webhook_id: str) -> bool: ...
