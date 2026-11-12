"""Activity ledger: every proposal made under a buyer's mandates, with what the rules decided and what was paid."""

from __future__ import annotations

import uuid
from collections import Counter

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
)

LIMIT = 200
CAPTURED_STATES = ("CAPTURED", "RECEIPT_CREATED", "REFUNDED")


def for_buyer(s: Session, buyer_id: uuid.UUID) -> dict:
    sessions = s.execute(
        select(PurchaseSession, MandateVersion, PurchaseMandate)
        .join(MandateVersion, MandateVersion.id == PurchaseSession.mandate_version_id)
        .join(PurchaseMandate, PurchaseMandate.id == MandateVersion.mandate_id)
        .where(PurchaseMandate.buyer_id == buyer_id)
        .order_by(PurchaseSession.created_at.desc())
        .limit(LIMIT)
    ).all()
    rows, by_rule, by_decision = [], Counter(), Counter()
    captured_minor, captured_count, currency = 0, 0, None
    for ps, version, mandate in sessions:
        product = s.get(Product, ps.proposed_product_id)
        evs = s.scalars(select(PolicyEvaluation).where(PolicyEvaluation.purchase_session_id == ps.id).order_by(PolicyEvaluation.evaluated_at)).all()
        decisive = next((e for e in reversed(evs) if e.decision != "ALLOW"), evs[-1] if evs else None)
        quote = s.get(ProductQuote, evs[0].quote_id) if evs else None
        co = s.scalars(select(CheckoutSession).where(CheckoutSession.purchase_session_id == ps.id)).first()
        pay = s.scalars(select(PaymentRecord).where(PaymentRecord.checkout_session_id == co.id)).first() if co else None
        receipt = s.scalars(select(PurchaseReceipt).where(PurchaseReceipt.checkout_session_id == co.id)).first() if co else None
        decision = decisive.decision if decisive else "REVIEW"
        failed = list(decisive.failed_constraints) if decisive else []
        by_decision[decision] += 1
        by_rule.update(failed)
        if co and co.state in CAPTURED_STATES and pay:
            captured_minor, captured_count, currency = captured_minor + pay.amount_minor, captured_count + 1, pay.currency
        rows.append({
            "purchase_session_id": str(ps.id), "at": ps.created_at.isoformat(), "mandate_id": str(mandate.id), "mandate_version": version.version,
            "proposed_by": ps.proposed_by, "product_id": product.provider_product_id, "product_title": product.title,
            "total_minor": quote.total_amount_minor if quote else None, "currency": quote.currency if quote else product.currency,
            "decision": decision, "refused_at": decisive.stage if decisive and decisive.decision != "ALLOW" else None, "failed": failed,
            "outcome": co.state if co else ps.status, "checkout_id": str(co.id) if co else None,
            "capture_id": pay.paypal_capture_id if pay else None, "receipt_id": str(receipt.id) if receipt else None,
        })  # fmt: skip
    return {
        "rows": rows,
        "stats": {
            "proposals": len(rows), "allowed": by_decision.get("ALLOW", 0), "refused": len(rows) - by_decision.get("ALLOW", 0),
            "by_agent": sum(1 for r in rows if r["proposed_by"] == "agent"), "captured_count": captured_count,
            "captured_minor": captured_minor, "currency": currency,
            "by_decision": dict(by_decision), "by_rule": [{"rule_id": k, "count": v} for k, v in by_rule.most_common()],
        },  # fmt: skip
        "limit": LIMIT,
    }
