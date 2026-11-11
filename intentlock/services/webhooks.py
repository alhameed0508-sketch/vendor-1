"""PayPal webhook processing: verify, store once, apply idempotently, reconcile with the local record."""

from __future__ import annotations

import json
import uuid
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from intentlock.db.models import CheckoutSession, PaymentRecord, WebhookEvent, utcnow
from intentlock.money import MoneyError, to_minor
from intentlock.payments.base import CaptureInfo, PaymentProvider, ProviderError
from intentlock.services import audit, checkout
from intentlock.settings import Settings

HANDLED = frozenset({"CHECKOUT.ORDER.APPROVED", "PAYMENT.CAPTURE.COMPLETED", "PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.PENDING", "PAYMENT.CAPTURE.REFUNDED"})


class WebhookError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _minimise(event: dict) -> dict:
    r = event.get("resource") or {}
    return {
        "id": event.get("id"), "event_type": event.get("event_type"), "create_time": event.get("create_time"),
        "resource_type": event.get("resource_type"),
        "resource": {"id": r.get("id"), "status": r.get("status"), "amount": r.get("amount"), "custom_id": r.get("custom_id"),
                     "order_id": ((r.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")},
    }  # fmt: skip


def _find_checkout(s: Session, event_type: str, resource: dict) -> CheckoutSession | None:
    if event_type.startswith("CHECKOUT.ORDER."):
        order_id = resource.get("id")
    else:
        order_id = ((resource.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id")
    if order_id:
        return s.scalars(select(CheckoutSession).where(CheckoutSession.paypal_order_id == order_id)).first()
    # Refund events carry the capture as an "up" link rather than an order id.
    for link in resource.get("links") or []:
        if link.get("rel") == "up" and "/captures/" in link.get("href", ""):
            capture_id = link["href"].rsplit("/captures/", 1)[1].split("/")[0]
            pay = s.scalars(select(PaymentRecord).where(PaymentRecord.paypal_capture_id == capture_id)).first()
            return s.get(CheckoutSession, pay.checkout_session_id) if pay else None
    if event_type.startswith("PAYMENT.CAPTURE.") and resource.get("id"):
        pay = s.scalars(select(PaymentRecord).where(PaymentRecord.paypal_capture_id == resource["id"])).first()
        return s.get(CheckoutSession, pay.checkout_session_id) if pay else None
    return None


def _capture_info(resource: dict, status: str) -> CaptureInfo | None:
    try:
        amount = resource["amount"]
        return CaptureInfo(capture_id=resource["id"], status=status, amount_minor=to_minor(amount["value"], amount["currency_code"]),
                           currency=amount["currency_code"], created_at=resource.get("create_time"))  # fmt: skip
    except (KeyError, TypeError, MoneyError):
        return None


def _apply(s: Session, co: CheckoutSession, event_type: str, resource: dict, settings: Settings, event_id: str) -> str:
    ctx = checkout.context(s, co)
    note = {"correlation_id": ctx.mandate.id, "aggregate_type": "checkout", "aggregate_id": co.id, "actor_type": "paypal_webhook",
            "source_reference": f"paypal_event:{event_id}"}  # fmt: skip
    if event_type == "CHECKOUT.ORDER.APPROVED":
        if co.state not in ("PAYPAL_ORDER_CREATED", "PAYPAL_APPROVAL_CANCELLED"):
            return "IGNORED_STATE"
        checkout.transition(co, "BUYER_APPROVED")
        audit.record(s, **note, action="BUYER_APPROVED", data={"via": "webhook"})
        return "PROCESSED"

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        cap = _capture_info(resource, "COMPLETED")
        if cap is None:
            return "IGNORED_MALFORMED"
        payment = s.scalars(select(PaymentRecord).where(PaymentRecord.checkout_session_id == co.id)).first()
        if payment is None or payment.status != "COMPLETED":
            if co.state not in ("CAPTURE_REQUESTED", "RECONCILIATION_REQUIRED"):
                # PayPal reports a capture this service never requested. Flag it; do not invent a state.
                co.reconciliation_status = "MISMATCH"
                audit.record(s, **note, action="UNEXPECTED_CAPTURE_REPORTED", data={"capture_id": cap.capture_id, "state": co.state})
                return "IGNORED_STATE"
            checkout.record_capture(s, co, cap, settings, "webhook")
            payment = s.scalars(select(PaymentRecord).where(PaymentRecord.checkout_session_id == co.id)).first()
        same = payment.paypal_capture_id == cap.capture_id and payment.amount_minor == cap.amount_minor and payment.currency == cap.currency
        same = same and cap.amount_minor == ctx.quote.total_amount_minor
        co.reconciliation_status = "VERIFIED" if same else "MISMATCH"
        audit.record(s, **note, action="WEBHOOK_RECONCILED", data={"capture_id": cap.capture_id, "result": co.reconciliation_status})
        return "PROCESSED"

    if event_type == "PAYMENT.CAPTURE.DENIED":
        if co.state not in ("CAPTURE_REQUESTED", "RECONCILIATION_REQUIRED"):
            return "IGNORED_STATE"
        checkout.transition(co, "CAPTURE_DENIED")
        ctx.ps.status, co.last_reason = co.state, "PayPal denied the capture."
        audit.record(s, **note, action="CAPTURE_DENIED", data={"via": "webhook"})
        return "PROCESSED"

    if event_type == "PAYMENT.CAPTURE.PENDING":
        audit.record(s, **note, action="CAPTURE_PENDING_REPORTED", data={"capture_id": resource.get("id")})
        return "PROCESSED"

    if event_type == "PAYMENT.CAPTURE.REFUNDED":
        if co.state not in ("CAPTURED", "RECEIPT_CREATED"):
            return "IGNORED_STATE"
        checkout.transition(co, "REFUNDED")
        ctx.ps.status = co.state
        payment = s.scalars(select(PaymentRecord).where(PaymentRecord.checkout_session_id == co.id)).first()
        if payment:
            payment.status = "REFUNDED"
        audit.record(s, **note, action="REFUNDED", data={"refund_id": resource.get("id")})
        return "PROCESSED"
    return "IGNORED_TYPE"


def handle(s: Session, provider: PaymentProvider, settings: Settings, headers: Mapping[str, str], raw_body: bytes) -> dict:
    """Verify and process one webhook delivery. Raises WebhookError when the delivery must not be accepted."""
    if not settings.paypal_webhook_id:
        raise WebhookError(503, "WEBHOOK_NOT_CONFIGURED", "PAYPAL_WEBHOOK_ID is not set, so webhooks cannot be verified")
    try:
        verified = provider.verify_webhook(headers, raw_body, settings.paypal_webhook_id)
    except ProviderError as exc:
        raise WebhookError(503, "VERIFICATION_UNAVAILABLE", "The signature could not be checked with PayPal; send the event again") from exc
    if not verified:
        raise WebhookError(400, "INVALID_SIGNATURE", "The webhook signature is not valid")
    try:
        event = json.loads(raw_body)
        event_id, event_type = event["id"], event["event_type"]
    except (ValueError, KeyError, TypeError) as exc:
        raise WebhookError(400, "MALFORMED_EVENT", "The webhook body is not a PayPal event") from exc
    resource = event.get("resource") or {}

    row = WebhookEvent(id=uuid.uuid4(), paypal_event_id=event_id, event_type=event_type, signature_verified=True, processing_status="RECEIVED",
                       payload_minimised=_minimise(event))  # fmt: skip
    s.add(row)
    try:
        s.flush()
    except IntegrityError:  # PayPal retried an event that is already stored
        s.rollback()
        return {"event_id": event_id, "duplicate": True, "processing_status": "DUPLICATE"}

    found = _find_checkout(s, event_type, resource) if event_type in HANDLED else None
    if event_type not in HANDLED:
        row.processing_status = "IGNORED_TYPE"
    elif found is None:
        row.processing_status = "QUARANTINED"  # stored, but no checkout of ours matches; nothing else is touched
    else:
        co = checkout.lock(s, found.id)
        row.checkout_session_id = co.id
        try:
            row.processing_status = _apply(s, co, event_type, resource, settings, event_id)
        except checkout.InvalidTransition:
            row.processing_status = "IGNORED_STATE"
    row.processed_at = utcnow()
    s.commit()
    return {"event_id": event_id, "duplicate": False, "processing_status": row.processing_status}
