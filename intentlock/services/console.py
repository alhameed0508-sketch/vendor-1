"""Merchant console: store-wide figures, the purchase ledger, the rule register and the buyer's own lists.

Store-wide rows never carry typed request text or contact details. `mine` marks the viewer's own rows; only
those carry the ids the browser needs to open a mandate, checkout or receipt.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta

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
from intentlock.policy.engine import RULE_TITLES, RULES, fail_phrase, rule_key
from intentlock.services import audit, mandates, receipts

APPROVED_STATES = frozenset({"BUYER_APPROVED", "FINAL_POLICY_REVALIDATION", "CAPTURE_REQUESTED", "RECONCILIATION_REQUIRED",
                             "CAPTURED", "RECEIPT_CREATED", "REFUNDED", "CAPTURE_DENIED"})  # fmt: skip
CAPTURED_STATES = frozenset({"CAPTURED", "RECEIPT_CREATED", "REFUNDED"})
CHART_DAYS_FOR_ALL = 30


def _entries(s: Session, viewer_id: uuid.UUID | None) -> list[dict]:
    """Every proposal in the store, oldest first, numbered IL-0001 onwards in the order they were made."""
    sessions = s.execute(
        select(PurchaseSession, MandateVersion, PurchaseMandate)
        .join(MandateVersion, MandateVersion.id == PurchaseSession.mandate_version_id)
        .join(PurchaseMandate, PurchaseMandate.id == MandateVersion.mandate_id)
        .order_by(PurchaseSession.created_at, PurchaseSession.id)
    ).all()
    products = {p.id: p for p in s.scalars(select(Product))}
    quotes = {q.id: q for q in s.scalars(select(ProductQuote))}
    evals: dict[uuid.UUID, list[PolicyEvaluation]] = defaultdict(list)
    for e in s.scalars(select(PolicyEvaluation).order_by(PolicyEvaluation.evaluated_at)):
        evals[e.purchase_session_id].append(e)
    checkouts = {c.purchase_session_id: c for c in s.scalars(select(CheckoutSession))}
    payments = {p.checkout_session_id: p for p in s.scalars(select(PaymentRecord))}
    receipt_rows = {r.checkout_session_id: r for r in s.scalars(select(PurchaseReceipt))}

    out = []
    for n, (ps, version, mandate) in enumerate(sessions, start=1):
        product = products[ps.proposed_product_id]
        evs = evals.get(ps.id, [])
        decisive = next((e for e in reversed(evs) if e.decision != "ALLOW"), evs[-1] if evs else None)
        quote = quotes.get(evs[0].quote_id) if evs else None
        co = checkouts.get(ps.id)
        pay = payments.get(co.id) if co else None
        rc = receipt_rows.get(co.id) if co else None
        mine = viewer_id is not None and mandate.buyer_id == viewer_id
        captured = bool(co and co.state in CAPTURED_STATES and pay)
        out.append({
            "ref": f"IL-{n:04d}", "at": ps.created_at.isoformat(), "day": ps.created_at.date().isoformat(),
            "product_id": product.provider_product_id, "product_title": product.title, "seller_name": product.seller_name,
            "proposed_by": ps.proposed_by, "total_minor": quote.total_amount_minor if quote else None,
            "currency": quote.currency if quote else product.currency,
            "decision": decisive.decision if decisive else "REVIEW",
            "refused_at": decisive.stage if decisive and decisive.decision != "ALLOW" else None,
            "failed": list(decisive.failed_constraints) if decisive and decisive.decision != "ALLOW" else [],
            "outcome": co.state if co else ps.status,
            # Approved = the buyer approved in PayPal, including orders the final check then refused.
            "ordered": bool(co and co.paypal_order_id),
            "approved": bool(co and (co.state in APPROVED_STATES or any(e.stage == "PRE_CAPTURE" for e in evs))),
            "captured": captured, "captured_minor": pay.amount_minor if captured else 0,
            "verified": bool(co and co.reconciliation_status == "VERIFIED"), "mismatch": bool(co and co.reconciliation_status == "MISMATCH"),
            "mine": mine,
            "mandate_id": str(mandate.id) if mine else None,
            "checkout_id": str(co.id) if mine and co else None,
            "receipt_id": str(rc.id) if mine and rc else None,
        })  # fmt: skip
    return out


def _since(days: int, now: datetime) -> datetime | None:
    return None if days <= 0 else now - timedelta(days=days)


def overview(s: Session, viewer_id: uuid.UUID | None, days: int, currency: str) -> dict:
    now = utcnow()
    since = _since(days, now)
    rows = [e for e in _entries(s, viewer_id) if since is None or datetime.fromisoformat(e["at"]) >= since]
    stopped = [e for e in rows if e["decision"] != "ALLOW"]

    rule_counts = Counter(rule for e in stopped for rule in e["failed"])
    chart_days = days if days > 0 else CHART_DAYS_FOR_ALL
    day_list = [(now - timedelta(days=i)).date().isoformat() for i in range(chart_days - 1, -1, -1)]
    per_day = {d: Counter() for d in day_list}
    for e in rows:
        if e["day"] in per_day:
            per_day[e["day"]][e["decision"]] += 1

    proposer = {who: {"total": 0, "stopped": 0} for who in ("agent", "buyer")}
    for e in rows:
        p = proposer.setdefault(e["proposed_by"], {"total": 0, "stopped": 0})
        p["total"] += 1
        p["stopped"] += e["decision"] != "ALLOW"

    intact, events = audit.verify_chain(s)
    webhooks = s.scalars(select(WebhookEvent).where(WebhookEvent.signature_verified.is_(True))).all()
    last_webhook = max((w.received_at for w in webhooks), default=None)
    mandate_rows = s.scalars(select(PurchaseMandate)).all()
    return {
        "days": days,
        "currency": currency,
        "statement": {
            "checked": len(rows),
            "stopped": len(stopped),
            "stopped_value_minor": sum(e["total_minor"] or 0 for e in stopped),
            "stopped_unpriced": sum(1 for e in stopped if e["total_minor"] is None),
            "stopped_by_decision": {d: sum(1 for e in stopped if e["decision"] == d) for d in ("BLOCK", "REAUTHORISE", "REVIEW")},
            "stopped_at_final_check": sum(1 for e in stopped if e["refused_at"] == "PRE_CAPTURE"),
            "refused_rules": sum(1 for e in stopped if e["refused_at"] != "PRE_CAPTURE"),
            "refused_rules_by_decision": {d: sum(1 for e in stopped if e["refused_at"] != "PRE_CAPTURE" and e["decision"] == d) for d in ("BLOCK", "REAUTHORISE", "REVIEW")},
            "refused_rules_value_minor": sum(e["total_minor"] or 0 for e in stopped if e["refused_at"] != "PRE_CAPTURE"),
            "refused_final": sum(1 for e in stopped if e["refused_at"] == "PRE_CAPTURE"),
            "refused_final_value_minor": sum(e["total_minor"] or 0 for e in stopped if e["refused_at"] == "PRE_CAPTURE"),
            "allowed": len(rows) - len(stopped),
            "ordered": sum(e["ordered"] for e in rows),
            "approved": sum(e["approved"] for e in rows),
            "captured": sum(e["captured"] for e in rows),
            "captured_minor": sum(e["captured_minor"] for e in rows),
            "verified": sum(e["verified"] for e in rows),
            "mismatched": sum(e["mismatch"] for e in rows),
        },
        "by_rule": [{"rule_id": r, "title": RULE_TITLES.get(rule_key(r), r), "reason": fail_phrase(r), "count": c} for r, c in rule_counts.most_common()],
        "per_day": [{"day": d, **{k: per_day[d].get(k, 0) for k in ("ALLOW", "BLOCK", "REAUTHORISE", "REVIEW")}} for d in day_list],
        "by_proposer": proposer,
        "recent": list(reversed(rows[-8:])),
        "mandates": {"total": len(mandate_rows), "confirmed": sum(1 for m in mandate_rows if m.status == "CONFIRMED")},
        "integrity": {"audit_intact": intact, "audit_events": events, "webhooks_verified": len(webhooks),
                      "last_webhook_at": last_webhook.isoformat() if last_webhook else None},  # fmt: skip
    }


def ledger(s: Session, viewer_id: uuid.UUID | None, mine_only: bool, limit: int = 300) -> dict:
    rows = _entries(s, viewer_id)
    if mine_only:
        rows = [e for e in rows if e["mine"]]
    shown = list(reversed(rows))[:limit]
    return {"rows": shown, "total": len(rows), "limit": limit, "mine_only": mine_only}


def rule_register(s: Session) -> dict:
    fired = Counter(rule_key(r) for e in _entries(s, None) if e["decision"] != "ALLOW" for r in e["failed"])
    return {
        "rules": [{"rule_id": rid, "stage": stage, "on_fail": on_fail, "title": title, "checks": checks, "fired": fired.get(rid, 0)}
                  for rid, stage, on_fail, title, checks in RULES],  # fmt: skip
    }


# ── the buyer's own lists ────────────────────────────────────────────────────
def my_mandates(s: Session, buyer_id: uuid.UUID) -> list[dict]:
    now = utcnow()
    out = []
    for m in s.scalars(select(PurchaseMandate).where(PurchaseMandate.buyer_id == buyer_id).order_by(PurchaseMandate.created_at.desc())):
        version = mandates.current_version(s, m)
        spec = mandates.spec_of(version)
        version_ids = select(MandateVersion.id).where(MandateVersion.mandate_id == m.id)
        proposals = s.scalars(select(PurchaseSession).where(PurchaseSession.mandate_version_id.in_(version_ids))).all()
        out.append({
            "mandate_id": str(m.id), "version": version.version, "status": mandates.effective_status(m, spec, now), "source": m.source,
            "request": m.original_request[:160], "category": spec.product.category, "condition": spec.product.condition.value,
            "quantity": spec.product.quantity, "budget_minor": spec.spending.maximum_total_minor, "currency": spec.currency,
            "expires_at": spec.expires_at.isoformat(), "created_at": m.created_at.isoformat(), "proposals": len(proposals),
            "paid": sum(1 for p in proposals if p.status in CAPTURED_STATES),
        })  # fmt: skip
    return out


def my_checkouts(s: Session, buyer_id: uuid.UUID) -> list[dict]:
    rows = s.execute(
        select(CheckoutSession, PurchaseSession, MandateVersion)
        .join(PurchaseSession, PurchaseSession.id == CheckoutSession.purchase_session_id)
        .join(MandateVersion, MandateVersion.id == PurchaseSession.mandate_version_id)
        .join(PurchaseMandate, PurchaseMandate.id == MandateVersion.mandate_id)
        .where(PurchaseMandate.buyer_id == buyer_id)
        .order_by(CheckoutSession.created_at.desc())
    ).all()
    out = []
    for co, ps, version in rows:
        product = s.get(Product, ps.proposed_product_id)
        quote = s.get(ProductQuote, co.quote_id)
        pay = s.scalars(select(PaymentRecord).where(PaymentRecord.checkout_session_id == co.id)).first()
        rc = s.scalars(select(PurchaseReceipt).where(PurchaseReceipt.checkout_session_id == co.id)).first()
        out.append({
            "checkout_id": str(co.id), "created_at": co.created_at.isoformat(), "updated_at": co.updated_at.isoformat(),
            "mandate_id": str(version.mandate_id), "product_title": product.title, "total_minor": quote.total_amount_minor, "currency": quote.currency,
            "state": co.state, "reconciliation": co.reconciliation_status, "reason": co.last_reason, "paypal_order_id": co.paypal_order_id,
            "capture_id": pay.paypal_capture_id if pay else None, "receipt_id": str(rc.id) if rc else None,
        })  # fmt: skip
    return out


def my_receipts(s: Session, buyer_id: uuid.UUID, signing_key: str) -> list[dict]:
    out = []
    for co in my_checkouts(s, buyer_id):
        if not co["receipt_id"]:
            continue
        rc = s.get(PurchaseReceipt, uuid.UUID(co["receipt_id"]))
        pay = rc.receipt_snapshot["payment"]
        out.append({
            "receipt_id": co["receipt_id"], "issued_at": rc.created_at.isoformat(), "product_title": co["product_title"],
            "amount_minor": pay["amount_minor"], "currency": pay["currency"], "paypal_order_id": rc.paypal_order_id,
            "capture_id": rc.paypal_capture_id, "state": co["state"], "reconciliation": co["reconciliation"],
            "receipt_hash": rc.receipt_hash, "share_path": f"/r/{receipts.share_token(rc.id, signing_key)}",
        })  # fmt: skip
    return out
