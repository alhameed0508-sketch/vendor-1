"""SQLAlchemy models. PostgreSQL is the target; SQLite is supported for local runs and unit tests.

Every table carries `tenant_id` so one deployment can serve more than one customer later.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
JsonType = JSON().with_variant(JSONB(), "postgresql")
BigIntPk = BigInteger().with_variant(Integer(), "sqlite")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UtcDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every backend (SQLite drops the timezone otherwise)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def _tenant() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False, default=DEFAULT_TENANT_ID, index=True)


def _created() -> Mapped[datetime]:
    return mapped_column(UtcDateTime, nullable=False, default=utcnow)


def _updated() -> Mapped[datetime]:
    return mapped_column(UtcDateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = _created()


class Buyer(Base):
    __tablename__ = "buyers"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    external_ref: Mapped[str | None] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = _created()


class PurchaseMandate(Base):
    __tablename__ = "purchase_mandates"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    buyer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("buyers.id"), nullable=False, index=True)
    original_request: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")  # ai | manual
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT", index=True)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class MandateVersion(Base):
    __tablename__ = "mandate_versions"
    __table_args__ = (UniqueConstraint("mandate_id", "version", name="uq_mandate_version"),)
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    mandate_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("purchase_mandates.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    structured_mandate: Mapped[dict] = mapped_column(JsonType, nullable=False)
    canonical_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(String(64))
    confirmed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = _created()


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("tenant_id", "source", "provider_product_id", name="uq_product_source_ref"),)
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    provider_product_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    attributes: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    seller_id: Mapped[str] = mapped_column(String(60), nullable=False)
    seller_name: Mapped[str] = mapped_column(String(120), nullable=False)
    merchant_checkout_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    availability_status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_stock")
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    unit_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shipping_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    tax_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class ProductQuote(Base):
    __tablename__ = "product_quotes"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("products.id"), nullable=False, index=True)
    mandate_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("mandate_versions.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    unit_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shipping_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    tax_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    total_amount_minor: Mapped[int | None] = mapped_column(BigInteger)
    quote_snapshot: Mapped[dict] = mapped_column(JsonType, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    created_at: Mapped[datetime] = _created()


class PurchaseSession(Base):
    __tablename__ = "purchase_sessions"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    mandate_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("mandate_versions.id"), nullable=False, index=True)
    agent_session_ref: Mapped[str | None] = mapped_column(String(120))
    proposed_by: Mapped[str] = mapped_column(String(16), nullable=False, default="buyer")  # buyer | agent
    proposed_product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("products.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class PolicyEvaluation(Base):
    __tablename__ = "policy_evaluations"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    purchase_session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("purchase_sessions.id"), nullable=False, index=True)
    quote_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("product_quotes.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(60), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    checks: Mapped[list] = mapped_column(JsonType, nullable=False)
    failed_constraints: Mapped[list] = mapped_column(JsonType, nullable=False)
    evaluated_at: Mapped[datetime] = _created()


class CheckoutSession(Base):
    __tablename__ = "checkout_sessions"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    purchase_session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("purchase_sessions.id"), nullable=False, unique=True)
    quote_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("product_quotes.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="paypal")
    paypal_order_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    paypal_create_request_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    paypal_capture_request_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    expected_payee: Mapped[dict | None] = mapped_column(JsonType)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reconciliation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    last_reason: Mapped[str | None] = mapped_column(Text)
    capture_requested_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class PaymentRecord(Base):
    __tablename__ = "payment_records"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    checkout_session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("checkout_sessions.id"), nullable=False, unique=True)
    paypal_order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload_minimised: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    paypal_event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    signature_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    checkout_session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("checkout_sessions.id"), index=True)
    payload_minimised: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    received_at: Mapped[datetime] = _created()
    processed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)


class AuditEvent(Base):
    """Append-only, hash-chained. `seq` orders the chain; `payload_hash` covers the previous hash and this event."""

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_aggregate", "aggregate_type", "aggregate_id"),)
    seq: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, unique=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = _tenant()
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # mandate id
    aggregate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    event_data: Mapped[dict] = mapped_column(JsonType, nullable=False, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created()


class PurchaseReceipt(Base):
    __tablename__ = "purchase_receipts"
    id: Mapped[uuid.UUID] = _pk()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    checkout_session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("checkout_sessions.id"), nullable=False, unique=True)
    mandate_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("mandate_versions.id"), nullable=False, index=True)
    paypal_order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    paypal_capture_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    receipt_snapshot: Mapped[dict] = mapped_column(JsonType, nullable=False)
    receipt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(String(128), nullable=False)
    signing_key_id: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created()
