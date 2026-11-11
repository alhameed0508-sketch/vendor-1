"""Checkout orchestrator: a persisted state machine around the payment provider.

Rules enforced here:
  * the order is built from the stored quote, never from browser input;
  * capture happens only after the approved order is re-fetched and re-evaluated, and only on ALLOW;
  * anything that cannot be verified means no capture (fail closed);
  * an unknown capture outcome is reconciled against the provider before any retry.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from intentlock.db.models import (
    CheckoutSession,
    MandateVersion,
    PaymentRecord,
    Product,
    ProductQuote,
    PurchaseMandate,
    PurchaseReceipt,
    PurchaseSession,
    utcnow,
)
from intentlock.domain import CheckStatus, Decision, Evaluation, ExpectedOrder, OrderFacts, OrderItem
from intentlock.money import display
from intentlock.payments.base import CaptureInfo, OrderRequest, OrderSnapshot, PaymentProvider, ProviderError, ProviderRejected, ProviderUnavailable
from intentlock.services import audit, catalog, mandates, purchases, receipts
from intentlock.settings import Settings

logger = logging.getLogger("intentlock.checkout")

STOP = frozenset({"BLOCKED", "REAUTHORISATION_REQUIRED", "REVIEW_REQUIRED", "EXPIRED"})
TRANSITIONS: dict[str, frozenset[str]] = {
    "POLICY_ALLOWED": frozenset({"PAYPAL_ORDER_CREATED"}) | STOP,
    "PAYPAL_ORDER_CREATED": frozenset({"BUYER_APPROVED", "PAYPAL_APPROVAL_CANCELLED"}) | STOP,
    "PAYPAL_APPROVAL_CANCELLED": frozenset({"BUYER_APPROVED"}) | STOP,
    "BUYER_APPROVED": frozenset({"FINAL_POLICY_REVALIDATION"}) | STOP,
    "FINAL_POLICY_REVALIDATION": frozenset({"CAPTURE_REQUESTED"}) | STOP,
    "CAPTURE_REQUESTED": frozenset({"CAPTURED", "CAPTURE_DENIED", "RECONCILIATION_REQUIRED"}) | STOP,
    "RECONCILIATION_REQUIRED": frozenset({"CAPTURED", "CAPTURE_DENIED", "CAPTURE_REQUESTED"}) | STOP,
    "CAPTURED": frozenset({"RECEIPT_CREATED", "REFUNDED"}),
    "RECEIPT_CREATED": frozenset({"REFUNDED"}),
}
FINISHED = frozenset({"CAPTURED", "RECEIPT_CREATED", "REFUNDED", "CAPTURE_DENIED"}) | STOP
AWAITING_APPROVAL = frozenset({"PAYPAL_ORDER_CREATED", "PAYPAL_APPROVAL_CANCELLED", "BUYER_APPROVED"})
DECISION_STATE = {Decision.BLOCK: "BLOCKED", Decision.REAUTHORISE: "REAUTHORISATION_REQUIRED", Decision.REVIEW: "REVIEW_REQUIRED"}
IN_FLIGHT_WINDOW = timedelta(seconds=30)


class CheckoutError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class InvalidTransition(CheckoutError):
    def __init__(self, current: str, new: str) -> None:
        super().__init__(409, "INVALID_STATE_TRANSITION", f"Checkout cannot move from {current} to {new}")


def transition(co: CheckoutSession, new: str) -> None:
    if new not in TRANSITIONS.get(co.state, frozenset()):
        raise InvalidTransition(co.state, new)
    co.state = new


@dataclass
class Ctx:
    ps: PurchaseSession
    quote: ProductQuote
    version: MandateVersion
    mandate: PurchaseMandate
    product: Product


def context(s: Session, co: CheckoutSession) -> Ctx:
    ps = s.get(PurchaseSession, co.purchase_session_id)
    version = s.get(MandateVersion, ps.mandate_version_id)
    return Ctx(ps=ps, quote=s.get(ProductQuote, co.quote_id), version=version, mandate=s.get(PurchaseMandate, version.mandate_id),
               product=s.get(Product, ps.proposed_product_id))  # fmt: skip


def lock(s: Session, checkout_id: uuid.UUID) -> CheckoutSession:
    """Load the checkout with a row lock (PostgreSQL), so two finalize calls cannot both proceed."""
    co = s.execute(select(CheckoutSession).where(CheckoutSession.id == checkout_id).with_for_update()).scalar_one_or_none()
    if co is None:
        raise CheckoutError(404, "CHECKOUT_NOT_FOUND", "Checkout not found")
    s.refresh(co)
    return co


def _order_facts(o: OrderSnapshot) -> OrderFacts:
    return OrderFacts(order_id=o.order_id, status=o.status, currency=o.currency, total_minor=o.total_minor, payee_merchant_id=o.payee_merchant_id,
                      payee_email=o.payee_email, purchase_unit_count=o.purchase_unit_count, custom_id=o.custom_id, has_capture=bool(o.captures),
                      items=[OrderItem(sku=i.sku, quantity=i.quantity, unit_amount_minor=i.unit_amount_minor) for i in o.items])  # fmt: skip


def _reasons(ev: Evaluation) -> str:
    return " ".join(c.reason for c in ev.checks if c.status is not CheckStatus.PASS)[:1000]


def _refuse(s: Session, co: CheckoutSession, ctx: Ctx, ev: Evaluation, action: str) -> None:
    row = purchases.store_evaluation(s, ctx.ps.id, ctx.quote.id, ev)
    transition(co, DECISION_STATE[ev.decision])
    ctx.ps.status = co.state
    co.last_reason = _reasons(ev)
    audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action=action,
                 source_reference=f"policy_evaluation:{row.id}",
                 data={"decision": ev.decision.value, "failed": ev.failed_constraints, "stage": ev.stage, "state": co.state})  # fmt: skip


# ── create ───────────────────────────────────────────────────────────────────
def create(s: Session, ps: PurchaseSession, actor_id) -> CheckoutSession:
    """Open a checkout for an allowed proposal. One checkout per proposal; a repeat call returns it."""
    existing = s.scalars(select(CheckoutSession).where(CheckoutSession.purchase_session_id == ps.id)).first()
    if existing:
        return existing
    if ps.status != "POLICY_ALLOWED":
        raise CheckoutError(409, "POLICY_NOT_ALLOWED", f"This proposal is {ps.status}; only an allowed proposal can be checked out")
    evs = purchases.evaluations_for(s, ps.id)
    quote = s.get(ProductQuote, evs[0].quote_id)
    if quote.total_amount_minor is None or quote.shipping_amount_minor is None or quote.tax_amount_minor is None:
        raise CheckoutError(409, "QUOTE_INCOMPLETE", "The quote has no complete total")
    if quote.expires_at <= utcnow():
        raise CheckoutError(409, "QUOTE_EXPIRED", "The quote has expired; evaluate the product again")
    version = s.get(MandateVersion, ps.mandate_version_id)
    co = CheckoutSession(id=uuid.uuid4(), purchase_session_id=ps.id, quote_id=quote.id, state="POLICY_ALLOWED",
                         paypal_create_request_id=f"il-create-{uuid.uuid4()}")  # fmt: skip
    s.add(co)
    try:
        s.flush()
    except IntegrityError:  # a concurrent request created it first
        s.rollback()
        return s.scalars(select(CheckoutSession).where(CheckoutSession.purchase_session_id == ps.id)).one()
    audit.record(s, correlation_id=version.mandate_id, aggregate_type="checkout", aggregate_id=co.id, action="CHECKOUT_CREATED",
                 actor_type="buyer", actor_id=actor_id, data={"quote_id": str(quote.id), "state": co.state})  # fmt: skip
    s.commit()
    return co


def create_order(s: Session, checkout_id: uuid.UUID, provider: PaymentProvider, settings: Settings) -> CheckoutSession:
    """Create the provider order from the stored quote, after a fresh policy evaluation."""
    co = lock(s, checkout_id)
    if co.paypal_order_id or co.state != "POLICY_ALLOWED":
        s.rollback()
        return co
    ctx = context(s, co)
    now = utcnow()
    ev = purchases.safe_evaluate(mandate=ctx.mandate, version=ctx.version, product=ctx.product, quote=purchases.quote_facts(ctx.quote, ctx.product), now=now)
    if ev.decision is not Decision.ALLOW:
        _refuse(s, co, ctx, ev, "ORDER_REFUSED")
        s.commit()
        return co
    q = ctx.quote
    request = OrderRequest(reference=str(co.id), title=ctx.product.title, sku=ctx.product.provider_product_id, quantity=q.quantity, currency=q.currency,
                           unit_amount_minor=q.unit_amount_minor, shipping_amount_minor=q.shipping_amount_minor,
                           tax_amount_minor=q.tax_amount_minor, total_amount_minor=q.total_amount_minor)  # fmt: skip
    try:
        order = provider.create_order(request, co.paypal_create_request_id)
    except ProviderUnavailable as exc:
        s.rollback()
        raise CheckoutError(503, "PAYMENT_PROVIDER_UNAVAILABLE", "PayPal could not be reached. No order was confirmed; trying again reuses the same request, so no duplicate is created.") from exc
    except ProviderRejected as exc:
        audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action="ORDER_CREATE_REJECTED",
                     source_reference="paypal", data={"name": exc.name, "issue": exc.issue, "debug_id": exc.debug_id})  # fmt: skip
        s.commit()
        raise CheckoutError(502, "PAYMENT_PROVIDER_REJECTED", f"PayPal rejected the order ({exc.issue or exc.name})") from exc

    problem = None
    if order.total_minor != q.total_amount_minor or order.currency != q.currency:
        problem = "PayPal created an order whose amount differs from the stored quote."
    elif settings.paypal_merchant_id and order.payee_merchant_id != settings.paypal_merchant_id:
        problem = "PayPal created the order for a payee that is not the configured merchant."
    elif not (order.payee_merchant_id or order.payee_email):
        problem = "PayPal did not return a payee for the order, so the payee cannot be verified later."
    co.paypal_order_id = order.order_id
    co.expected_payee = {"merchant_id": order.payee_merchant_id, "email": order.payee_email}
    if problem:
        transition(co, "BLOCKED")
        ctx.ps.status, co.last_reason = "BLOCKED", problem
    else:
        transition(co, "PAYPAL_ORDER_CREATED")
        ctx.ps.status = "PAYPAL_ORDER_CREATED"
    audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action="PAYPAL_ORDER_CREATED" if not problem else "ORDER_BLOCKED",
                 source_reference=f"paypal_order:{order.order_id}",
                 data={"order_id": order.order_id, "total_minor": order.total_minor, "currency": order.currency, "state": co.state, "reason": problem})  # fmt: skip
    s.commit()
    return co


def cancel(s: Session, checkout_id: uuid.UUID, actor_id) -> CheckoutSession:
    co = lock(s, checkout_id)
    if co.state == "PAYPAL_ORDER_CREATED":
        transition(co, "PAYPAL_APPROVAL_CANCELLED")
        ctx = context(s, co)
        audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action="PAYPAL_APPROVAL_CANCELLED",
                     actor_type="buyer", actor_id=actor_id, data={"state": co.state})  # fmt: skip
        s.commit()
    else:
        s.rollback()
    return co


# ── finalize ─────────────────────────────────────────────────────────────────
def _fetch_order(s: Session, co: CheckoutSession, ctx: Ctx, provider: PaymentProvider, action: str) -> OrderSnapshot:
    try:
        return provider.get_order(co.paypal_order_id)
    except (ProviderError, ValueError) as exc:
        audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action=action,
                     source_reference="paypal", data={"error": type(exc).__name__, "state": co.state})  # fmt: skip
        s.commit()
        raise CheckoutError(503, "VERIFICATION_UNAVAILABLE", "The PayPal order could not be retrieved, so it was not verified and nothing was captured.") from exc


def _pre_capture(s: Session, co: CheckoutSession, ctx: Ctx, order: OrderSnapshot) -> Evaluation:
    payee = co.expected_payee or {}
    expected = ExpectedOrder(order_id=co.paypal_order_id, payee_merchant_id=payee.get("merchant_id"), payee_email=payee.get("email"),
                             custom_id=str(co.id), sku=ctx.product.provider_product_id)  # fmt: skip
    return purchases.safe_evaluate(mandate=ctx.mandate, version=ctx.version, product=ctx.product, quote=purchases.quote_facts(ctx.quote, ctx.product),
                                   now=utcnow(), order=_order_facts(order), expected=expected)  # fmt: skip


def finalize(s: Session, checkout_id: uuid.UUID, provider: PaymentProvider, settings: Settings) -> CheckoutSession:
    """Retrieve the approved order, revalidate, and capture only if every check passes. Safe to call twice."""
    co = lock(s, checkout_id)
    if co.state in FINISHED:
        s.rollback()
        return co
    if co.state in ("CAPTURE_REQUESTED", "RECONCILIATION_REQUIRED"):
        return _reconcile(s, co, provider, settings)
    if co.state not in AWAITING_APPROVAL or not co.paypal_order_id:
        s.rollback()
        raise CheckoutError(409, "ORDER_NOT_CREATED", "No PayPal order exists for this checkout yet")
    ctx = context(s, co)
    order = _fetch_order(s, co, ctx, provider, "FINAL_VERIFICATION_UNAVAILABLE")

    if order.status == "VOIDED":
        transition(co, "EXPIRED")
        ctx.ps.status, co.last_reason = "EXPIRED", "PayPal reports the order as voided."
        audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action="ORDER_EXPIRED",
                     source_reference=f"paypal_order:{order.order_id}", data={"state": co.state})  # fmt: skip
        s.commit()
        return co
    if order.status != "APPROVED" and not order.captures:
        co.last_reason = f"PayPal reports the order as {order.status}. The buyer has not approved it yet, so nothing was captured."
        s.commit()
        return co

    if co.state != "BUYER_APPROVED":
        transition(co, "BUYER_APPROVED")
        audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action="BUYER_APPROVED",
                     source_reference=f"paypal_order:{order.order_id}", data={"order_status": order.status})  # fmt: skip
    transition(co, "FINAL_POLICY_REVALIDATION")
    ev = _pre_capture(s, co, ctx, order)
    if ev.decision is not Decision.ALLOW:
        _refuse(s, co, ctx, ev, "CAPTURE_REFUSED")
        s.commit()
        return co
    row = purchases.store_evaluation(s, ctx.ps.id, ctx.quote.id, ev)
    audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="policy_evaluation", aggregate_id=row.id, action="FINAL_VERIFICATION_PASSED",
                 source_reference=f"paypal_order:{order.order_id}", data={"decision": ev.decision.value, "checks": len(ev.checks)})  # fmt: skip
    co.paypal_capture_request_id = co.paypal_capture_request_id or f"il-capture-{co.id}"
    co.capture_requested_at = utcnow()
    transition(co, "CAPTURE_REQUESTED")
    ctx.ps.status, co.last_reason = "CAPTURE_REQUESTED", None
    audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action="CAPTURE_REQUESTED",
                 data={"order_id": co.paypal_order_id, "request_id": co.paypal_capture_request_id})  # fmt: skip
    s.commit()  # persisted before the external call; releases the row lock
    return _capture(s, co.id, provider, settings)


def _capture(s: Session, checkout_id: uuid.UUID, provider: PaymentProvider, settings: Settings) -> CheckoutSession:
    co = s.get(CheckoutSession, checkout_id)
    try:
        result = provider.capture_order(co.paypal_order_id, co.paypal_capture_request_id)
    except (ProviderUnavailable, ValueError) as exc:
        co = lock(s, checkout_id)
        if co.state == "CAPTURE_REQUESTED":
            transition(co, "RECONCILIATION_REQUIRED")
            co.last_reason = "PayPal did not confirm the capture. The outcome is unknown and will be checked with PayPal before anything is retried."
            ctx = context(s, co)
            ctx.ps.status = co.state
            audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action="CAPTURE_OUTCOME_UNKNOWN",
                         source_reference="paypal", data={"error": type(exc).__name__})  # fmt: skip
        s.commit()
        return co
    except ProviderRejected as exc:
        co = lock(s, checkout_id)
        if exc.issue == "ORDER_ALREADY_CAPTURED":
            return _reconcile(s, co, provider, settings)
        if co.state == "CAPTURE_REQUESTED":
            transition(co, "CAPTURE_DENIED")
            co.last_reason = f"PayPal declined the capture ({exc.issue or exc.name})."
            ctx = context(s, co)
            ctx.ps.status = co.state
            audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action="CAPTURE_DENIED",
                         source_reference="paypal", data={"name": exc.name, "issue": exc.issue, "debug_id": exc.debug_id})  # fmt: skip
        s.commit()
        return co
    co = lock(s, checkout_id)
    record_capture(s, co, result.captures[0] if result.captures else None, settings, "capture_response")
    s.commit()
    return co


def record_capture(s: Session, co: CheckoutSession, cap: CaptureInfo | None, settings: Settings, source: str) -> None:
    """Store the provider's capture result and move the state. The caller holds the lock and commits."""
    if co.state in ("CAPTURED", "RECEIPT_CREATED", "REFUNDED"):
        return
    ctx = context(s, co)
    if cap is None:
        if co.state == "CAPTURE_REQUESTED":
            transition(co, "RECONCILIATION_REQUIRED")
            co.last_reason = "PayPal answered without a capture record. The payment will be checked with PayPal."
        return
    payment = s.scalars(select(PaymentRecord).where(PaymentRecord.checkout_session_id == co.id)).first()
    if payment is None:
        payment = PaymentRecord(id=uuid.uuid4(), checkout_session_id=co.id, paypal_order_id=co.paypal_order_id)
        s.add(payment)
    payment.paypal_capture_id, payment.status, payment.currency, payment.amount_minor = cap.capture_id, cap.status, cap.currency, cap.amount_minor
    payment.payload_minimised = {"capture_id": cap.capture_id, "status": cap.status, "created_at": cap.created_at, "source": source}
    s.flush()
    base = {"correlation_id": ctx.mandate.id, "aggregate_type": "payment", "aggregate_id": payment.id, "source_reference": f"paypal_capture:{cap.capture_id}"}
    info = {"capture_id": cap.capture_id, "status": cap.status, "amount_minor": cap.amount_minor, "currency": cap.currency, "via": source}
    if cap.status == "COMPLETED":
        if cap.amount_minor != ctx.quote.total_amount_minor or cap.currency != ctx.quote.currency:
            co.reconciliation_status = "MISMATCH"
            co.last_reason = f"PayPal captured {display(cap.amount_minor, cap.currency)}, which differs from the approved quote."
        transition(co, "CAPTURED")
        audit.record(s, **base, action="CAPTURED", data=info)
        receipts.issue(s, co, payment, settings.resolved_receipt_key)
        transition(co, "RECEIPT_CREATED")
        ctx.ps.status = co.state
    elif cap.status == "PENDING":
        if co.state == "CAPTURE_REQUESTED":
            transition(co, "RECONCILIATION_REQUIRED")
        co.last_reason = "PayPal holds the capture as pending. It will be completed or denied by PayPal."
        ctx.ps.status = co.state
        audit.record(s, **base, action="CAPTURE_PENDING", data=info)
    else:
        transition(co, "CAPTURE_DENIED")
        co.last_reason = f"PayPal reports the capture as {cap.status}."
        ctx.ps.status = co.state
        audit.record(s, **base, action="CAPTURE_DENIED", data=info)


def _reconcile(s: Session, co: CheckoutSession, provider: PaymentProvider, settings: Settings) -> CheckoutSession:
    """Ask the provider what happened before doing anything else. The caller holds the lock."""
    ctx = context(s, co)
    order = _fetch_order(s, co, ctx, provider, "RECONCILIATION_UNAVAILABLE")
    if order.captures:
        record_capture(s, co, order.captures[0], settings, "reconciliation")
        s.commit()
        return co
    if order.status != "APPROVED":
        transition(co, "CAPTURE_DENIED")
        ctx.ps.status, co.last_reason = co.state, f"PayPal reports the order as {order.status} with no capture."
        audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action="RECONCILED_NO_CAPTURE",
                     source_reference=f"paypal_order:{order.order_id}", data={"order_status": order.status})  # fmt: skip
        s.commit()
        return co
    if co.state == "CAPTURE_REQUESTED" and co.capture_requested_at and utcnow() - co.capture_requested_at < IN_FLIGHT_WINDOW:
        s.rollback()  # another request is capturing right now
        return co
    ev = _pre_capture(s, co, ctx, order)
    if ev.decision is not Decision.ALLOW:
        _refuse(s, co, ctx, ev, "CAPTURE_REFUSED")
        s.commit()
        return co
    if co.state == "RECONCILIATION_REQUIRED":
        transition(co, "CAPTURE_REQUESTED")
    co.capture_requested_at = utcnow()
    ctx.ps.status = co.state
    audit.record(s, correlation_id=ctx.mandate.id, aggregate_type="checkout", aggregate_id=co.id, action="CAPTURE_RETRIED_AFTER_RECONCILIATION",
                 source_reference=f"paypal_order:{order.order_id}", data={"request_id": co.paypal_capture_request_id})  # fmt: skip
    s.commit()
    return _capture(s, co.id, provider, settings)


# ── views ────────────────────────────────────────────────────────────────────
def view(s: Session, co: CheckoutSession) -> dict:
    ctx = context(s, co)
    payment = s.scalars(select(PaymentRecord).where(PaymentRecord.checkout_session_id == co.id)).first()
    receipt = s.scalars(select(PurchaseReceipt).where(PurchaseReceipt.checkout_session_id == co.id)).first()
    return {
        "checkout_id": str(co.id),
        "state": co.state,
        "reconciliation_status": co.reconciliation_status,
        "reason": co.last_reason,
        "paypal_order_id": co.paypal_order_id,
        "mandate": {"mandate_id": str(ctx.mandate.id), "version": ctx.version.version, "canonical_hash": ctx.version.canonical_hash,
                    "status": mandates.effective_status(ctx.mandate, mandates.spec_of(ctx.version), utcnow()),
                    "is_current_version": ctx.version.version == ctx.mandate.current_version},  # fmt: skip
        "product": catalog.product_view(ctx.product),
        "quote": purchases.quote_view(ctx.quote),
        "evaluations": [purchases.evaluation_view(e) for e in purchases.evaluations_for(s, ctx.ps.id)],
        "payment": None if payment is None else {"capture_id": payment.paypal_capture_id, "status": payment.status,
                                                 "amount_minor": payment.amount_minor, "currency": payment.currency},  # fmt: skip
        "receipt_id": str(receipt.id) if receipt else None,
        "timeline": audit.timeline(s, ctx.mandate.id),
    }
