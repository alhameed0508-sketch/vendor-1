"""Purchase receipts and the provenance graph. Both are built only from stored PostgreSQL rows.

A receipt hash is a tamper-evident fingerprint of the stored snapshot, and the signature shows this service
issued it. Neither is a legal digital signature or proof of the buyer's identity.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from intentlock.db.models import (
    CheckoutSession,
    MandateVersion,
    PaymentRecord,
    PolicyEvaluation,
    Product,
    ProductQuote,
    PurchaseMandate,
    PurchaseReceipt,
    PurchaseSession,
    WebhookEvent,
    utcnow,
)
from intentlock.domain import canonical_json, sha256_hex
from intentlock.services import audit

SIGNING_KEY_ID = "hmac-sha256-k1"


def _sign(receipt_hash: str, key: str) -> str:
    return hmac.new(key.encode("utf-8"), receipt_hash.encode("utf-8"), hashlib.sha256).hexdigest()


def issue(s: Session, co: CheckoutSession, payment: PaymentRecord, signing_key: str) -> PurchaseReceipt:
    """Create the receipt for a captured checkout. One per checkout; a second call returns the first."""
    existing = s.scalars(select(PurchaseReceipt).where(PurchaseReceipt.checkout_session_id == co.id)).first()
    if existing:
        return existing
    ps = s.get(PurchaseSession, co.purchase_session_id)
    quote = s.get(ProductQuote, co.quote_id)
    version = s.get(MandateVersion, ps.mandate_version_id)
    mandate = s.get(PurchaseMandate, version.mandate_id)
    product = s.get(Product, ps.proposed_product_id)
    evaluations = s.scalars(select(PolicyEvaluation).where(PolicyEvaluation.purchase_session_id == ps.id).order_by(PolicyEvaluation.evaluated_at)).all()
    receipt_id = uuid.uuid4()
    snapshot = {
        "receipt_id": str(receipt_id),
        "issued_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "original_request": mandate.original_request,
        "mandate": {"mandate_id": str(mandate.id), "version": version.version, "canonical_hash": version.canonical_hash,
                    "confirmed_at": version.confirmed_at.strftime("%Y-%m-%dT%H:%M:%SZ") if version.confirmed_at else None,
                    "source": mandate.source, "terms": version.structured_mandate},  # fmt: skip
        "product": {"product_id": product.provider_product_id, "title": product.title, "condition": product.condition,
                    "attributes": product.attributes, "seller_id": product.seller_id, "seller_name": product.seller_name,
                    "source": product.source, "synthetic": product.synthetic},  # fmt: skip
        "quote": {"quote_id": str(quote.id), "quantity": quote.quantity, "currency": quote.currency, "unit_amount_minor": quote.unit_amount_minor,
                  "shipping_amount_minor": quote.shipping_amount_minor, "tax_amount_minor": quote.tax_amount_minor,
                  "total_amount_minor": quote.total_amount_minor},  # fmt: skip
        "policy": [{"evaluation_id": str(e.id), "stage": e.stage, "policy_version": e.policy_version, "decision": e.decision,
                    "checks": [{"rule_id": c["rule_id"], "status": c["status"]} for c in e.checks]} for e in evaluations],  # fmt: skip
        "payment": {"provider": co.provider, "order_id": payment.paypal_order_id, "capture_id": payment.paypal_capture_id, "status": payment.status,
                    "amount_minor": payment.amount_minor, "currency": payment.currency, "payee": co.expected_payee},  # fmt: skip
        "checkout_id": str(co.id),
    }
    receipt_hash = sha256_hex(canonical_json(snapshot))
    receipt = PurchaseReceipt(id=receipt_id, checkout_session_id=co.id, mandate_version_id=version.id, paypal_order_id=payment.paypal_order_id,
                              paypal_capture_id=payment.paypal_capture_id, receipt_snapshot=snapshot, receipt_hash=receipt_hash,
                              signature=_sign(receipt_hash, signing_key), signing_key_id=SIGNING_KEY_ID)  # fmt: skip
    s.add(receipt)
    audit.record(s, correlation_id=mandate.id, aggregate_type="receipt", aggregate_id=receipt_id, action="RECEIPT_CREATED",
                 data={"receipt_hash": receipt_hash, "capture_id": payment.paypal_capture_id})  # fmt: skip
    return receipt


def share_token(receipt_id, signing_key: str) -> str:
    """A link token only the receipt's owner can obtain: the receipt id plus a keyed hash of it."""
    tag = hmac.new(signing_key.encode("utf-8"), f"share:{receipt_id}".encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{receipt_id}.{tag}"


def receipt_id_from_token(token: str, signing_key: str) -> uuid.UUID | None:
    rid, _, _tag = token.partition(".")
    try:
        parsed = uuid.UUID(rid)
    except ValueError:
        return None
    return parsed if hmac.compare_digest(share_token(parsed, signing_key), token) else None


def public_view(s: Session, receipt: PurchaseReceipt, signing_key: str) -> dict:
    """The receipt as shown to anyone holding its share link: read-only, with contact details removed."""
    v = view(s, receipt, signing_key)
    snapshot = {**v["receipt"], "payment": {**v["receipt"]["payment"]}}
    payee = snapshot["payment"].get("payee") or {}
    snapshot["payment"]["payee"] = {"merchant_id": payee.get("merchant_id")}  # no email on a shared page
    mandate = s.get(PurchaseMandate, uuid.UUID(snapshot["mandate"]["mandate_id"]))
    return {**v, "receipt": snapshot, "shared": True, "share_path": None, "graph": graph(s, mandate)}


def view(s: Session, receipt: PurchaseReceipt, signing_key: str) -> dict:
    co = s.get(CheckoutSession, receipt.checkout_session_id)
    recomputed = sha256_hex(canonical_json(receipt.receipt_snapshot))
    events = s.scalars(select(WebhookEvent).where(WebhookEvent.checkout_session_id == co.id).order_by(WebhookEvent.received_at)).all()
    mandate_id = receipt.receipt_snapshot["mandate"]["mandate_id"]
    return {
        "receipt_id": str(receipt.id),
        "shared": False,
        "share_path": f"/r/{share_token(receipt.id, signing_key)}",
        "receipt": receipt.receipt_snapshot,
        "receipt_hash": receipt.receipt_hash,
        "signature": receipt.signature,
        "signing_key_id": receipt.signing_key_id,
        "integrity": {"hash_matches": recomputed == receipt.receipt_hash,
                      "signature_matches": hmac.compare_digest(_sign(receipt.receipt_hash, signing_key), receipt.signature)},  # fmt: skip
        "checkout_state": co.state,
        "reconciliation": {"status": co.reconciliation_status,
                           "webhook_events": [{"event_id": e.paypal_event_id, "type": e.event_type, "verified": e.signature_verified,
                                               "processing": e.processing_status, "received_at": e.received_at.isoformat()} for e in events]},  # fmt: skip
        "timeline": audit.timeline(s, mandate_id),
    }


def graph(s: Session, mandate: PurchaseMandate) -> dict:
    """Purchase provenance as nodes and edges, derived from PostgreSQL. Evidence organisation, not proof of anything."""
    nodes, edges = [], []

    def node(kind: str, ident, label: str, **extra) -> str:
        nid = f"{kind}:{ident}"
        nodes.append({"id": nid, "kind": kind, "label": label, **extra})
        return nid

    def edge(a: str, b: str, rel: str, at=None, source: str = "postgresql") -> None:
        edges.append({"from": a, "to": b, "relationship": rel, "at": at.isoformat() if at else None, "source": source})

    buyer = node("Buyer", mandate.buyer_id, "Buyer")
    m = node("PurchaseMandate", mandate.id, "Mandate", status=mandate.status)
    edge(buyer, m, "CREATED", mandate.created_at)
    versions = s.scalars(select(MandateVersion).where(MandateVersion.mandate_id == mandate.id).order_by(MandateVersion.version)).all()
    for v in versions:
        vn = node("MandateVersion", v.id, f"Version {v.version}", hash=v.canonical_hash[:12], confirmed=v.confirmed_at is not None)
        edge(m, vn, "CONFIRMED_AS" if v.confirmed_at else "DRAFTED_AS", v.confirmed_at or v.created_at)
        for ps in s.scalars(select(PurchaseSession).where(PurchaseSession.mandate_version_id == v.id).order_by(PurchaseSession.created_at)):
            product = s.get(Product, ps.proposed_product_id)
            sn = node("AgentSession" if ps.proposed_by == "agent" else "Proposal", ps.id, "Agent proposal" if ps.proposed_by == "agent" else "Buyer selection", status=ps.status)
            edge(vn, sn, "EXECUTED_BY", ps.created_at)
            pn = node("Product", f"{ps.id}:{product.provider_product_id}", product.title)
            edge(sn, pn, "PROPOSED", ps.created_at, product.source)
            mn = node("Merchant", f"{ps.id}:{product.seller_id}", product.seller_name)
            edge(pn, mn, "SOLD_BY", None, product.source)
            last = sn
            for ev in s.scalars(select(PolicyEvaluation).where(PolicyEvaluation.purchase_session_id == ps.id).order_by(PolicyEvaluation.evaluated_at)):
                en = node("PolicyEvaluation", ev.id, f"{'Final check' if ev.stage == 'PRE_CAPTURE' else 'Policy check'}: {ev.decision}", decision=ev.decision)
                edge(last, en, "EVALUATED_BY", ev.evaluated_at)
            co = s.scalars(select(CheckoutSession).where(CheckoutSession.purchase_session_id == ps.id)).first()
            if not co:
                continue
            cn = node("Checkout", co.id, "Checkout", state=co.state)
            edge(sn, cn, "CHECKED_OUT_AS", co.created_at)
            if co.paypal_order_id:
                on = node("PayPalOrder", co.paypal_order_id, f"PayPal order {co.paypal_order_id}")
                edge(cn, on, "CREATED_ORDER", co.created_at, "paypal")
                pay = s.scalars(select(PaymentRecord).where(PaymentRecord.checkout_session_id == co.id)).first()
                if pay and pay.paypal_capture_id:
                    cap = node("PaymentCapture", pay.paypal_capture_id, f"Capture {pay.paypal_capture_id}", status=pay.status)
                    edge(on, cap, "CAPTURED_AS", pay.created_at, "paypal")
                    for wh in s.scalars(select(WebhookEvent).where(WebhookEvent.checkout_session_id == co.id, WebhookEvent.signature_verified.is_(True))):
                        wn = node("Webhook", wh.paypal_event_id, "Verified webhook", event_type=wh.event_type)
                        edge(cap, wn, "RECONCILED_BY", wh.received_at, "paypal_webhook")
    return {"mandate_id": str(mandate.id), "source": "postgresql", "nodes": nodes, "edges": edges}
