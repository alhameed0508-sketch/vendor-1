"""Proposals: turn a selected product into a server-owned quote and a stored policy evaluation."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from intentlock.db.models import MandateVersion, PolicyEvaluation, Product, ProductQuote, PurchaseMandate, PurchaseSession, utcnow
from intentlock.domain import Decision, Evaluation, ExpectedOrder, OrderFacts, QuoteFacts
from intentlock.policy import engine
from intentlock.services import audit, catalog, mandates

logger = logging.getLogger("intentlock.purchases")
SESSION_STATUS = {
    Decision.ALLOW: "POLICY_ALLOWED",
    Decision.BLOCK: "BLOCKED",
    Decision.REAUTHORISE: "REAUTHORISATION_REQUIRED",
    Decision.REVIEW: "REVIEW_REQUIRED",
}


def build_quote(product: Product, quantity: int, now: datetime, ttl_minutes: int, quote_id: str = "preview") -> QuoteFacts:
    """Server-side price calculation. Shipping is per order, tax is per unit. Unknown parts stay unknown."""
    ship = product.shipping_amount_minor
    tax = None if product.tax_amount_minor is None else product.tax_amount_minor * quantity
    total = None if ship is None or tax is None else product.unit_amount_minor * quantity + ship + tax
    return QuoteFacts(quote_id=quote_id, product_id=product.provider_product_id, quantity=quantity, currency=product.currency,
                      unit_amount_minor=product.unit_amount_minor, shipping_amount_minor=ship, tax_amount_minor=tax,
                      total_amount_minor=total, expires_at=now + timedelta(minutes=ttl_minutes))  # fmt: skip


def quote_facts(q: ProductQuote, product: Product) -> QuoteFacts:
    return QuoteFacts(quote_id=str(q.id), product_id=product.provider_product_id, quantity=q.quantity, currency=q.currency,
                      unit_amount_minor=q.unit_amount_minor, shipping_amount_minor=q.shipping_amount_minor,
                      tax_amount_minor=q.tax_amount_minor, total_amount_minor=q.total_amount_minor, expires_at=q.expires_at)  # fmt: skip


def safe_evaluate(*, mandate: PurchaseMandate, version: MandateVersion, product: Product, quote: QuoteFacts, now: datetime,
                  order: OrderFacts | None = None, expected: ExpectedOrder | None = None) -> Evaluation:  # fmt: skip
    """Run the engine. Any internal failure becomes REVIEW, never ALLOW."""
    stage = "PRE_CAPTURE" if order is not None else "PRE_ORDER"
    try:
        return engine.evaluate(mandate=mandates.spec_of(version), state=mandates.state_of(mandate, version),
                               offer=catalog.offer_of(product), quote=quote, now=now, order=order, expected=expected)  # fmt: skip
    except Exception:  # noqa: BLE001 - fail closed on anything
        logger.exception("Policy evaluation failed; failing closed")
        return engine.fail_closed(stage, "The policy engine could not complete the evaluation, so the purchase is not allowed.")


def store_evaluation(s: Session, session_id: uuid.UUID, quote_id: uuid.UUID, ev: Evaluation) -> PolicyEvaluation:
    row = PolicyEvaluation(id=uuid.uuid4(), purchase_session_id=session_id, quote_id=quote_id, stage=ev.stage, policy_version=ev.policy_version,
                           decision=ev.decision.value, checks=[c.model_dump(mode="json") for c in ev.checks], failed_constraints=ev.failed_constraints)  # fmt: skip
    s.add(row)
    s.flush()
    return row


def preview(s: Session, mandate: PurchaseMandate, product: Product, ttl_minutes: int) -> Evaluation:
    """Evaluate without storing anything. Used to label catalogue cards."""
    now = utcnow()
    version = mandates.current_version(s, mandate)
    quantity = mandates.spec_of(version).product.quantity
    return safe_evaluate(mandate=mandate, version=version, product=product, quote=build_quote(product, quantity, now, ttl_minutes), now=now)


def propose(s: Session, *, mandate: PurchaseMandate, product: Product, quantity: int | None, proposed_by: str, agent_session_ref: str | None,
            actor_id, ttl_minutes: int) -> PurchaseSession:  # fmt: skip
    """Store the proposal, a quote and its evaluation. Nothing is sent to the payment provider here."""
    now = utcnow()
    version = mandates.current_version(s, mandate)
    spec = mandates.spec_of(version)
    qty = quantity or spec.product.quantity
    ps = PurchaseSession(id=uuid.uuid4(), mandate_version_id=version.id, agent_session_ref=agent_session_ref, proposed_by=proposed_by,
                         proposed_product_id=product.id, status="PRODUCT_SELECTED")  # fmt: skip
    s.add(ps)
    s.flush()
    facts = build_quote(product, qty, now, ttl_minutes)
    quote = ProductQuote(id=uuid.uuid4(), product_id=product.id, mandate_version_id=version.id, quantity=qty, currency=facts.currency,
                         unit_amount_minor=facts.unit_amount_minor, shipping_amount_minor=facts.shipping_amount_minor,
                         tax_amount_minor=facts.tax_amount_minor, total_amount_minor=facts.total_amount_minor,
                         quote_snapshot={"product": catalog.product_view(product), "quantity": qty, "priced_at": now.isoformat()},
                         expires_at=facts.expires_at)  # fmt: skip
    s.add(quote)
    s.flush()
    ev = safe_evaluate(mandate=mandate, version=version, product=product, quote=quote_facts(quote, product), now=now)
    row = store_evaluation(s, ps.id, quote.id, ev)
    ps.status = SESSION_STATUS[ev.decision]
    common = {"correlation_id": mandate.id, "actor_type": proposed_by, "actor_id": actor_id}
    audit.record(s, **common, aggregate_type="purchase_session", aggregate_id=ps.id, action="PRODUCT_PROPOSED",
                 source_reference=product.source_reference, data={"product_id": product.provider_product_id, "quantity": qty})  # fmt: skip
    audit.record(s, correlation_id=mandate.id, aggregate_type="quote", aggregate_id=quote.id, action="QUOTE_CREATED",
                 data={"total_minor": facts.total_amount_minor, "currency": facts.currency, "expires_at": facts.expires_at.isoformat()})  # fmt: skip
    audit.record(s, correlation_id=mandate.id, aggregate_type="policy_evaluation", aggregate_id=row.id, action="POLICY_EVALUATED",
                 data={"stage": ev.stage, "decision": ev.decision.value, "failed": ev.failed_constraints, "policy_version": ev.policy_version})  # fmt: skip
    s.commit()
    return ps


def evaluations_for(s: Session, session_id: uuid.UUID) -> list[PolicyEvaluation]:
    return list(s.scalars(select(PolicyEvaluation).where(PolicyEvaluation.purchase_session_id == session_id).order_by(PolicyEvaluation.evaluated_at)))


def evaluation_view(row: PolicyEvaluation) -> dict:
    return {
        "evaluation_id": str(row.id), "stage": row.stage, "policy_version": row.policy_version, "decision": row.decision,
        "checks": row.checks, "failed_constraints": row.failed_constraints,
        "requires_buyer_reapproval": row.decision == Decision.REAUTHORISE.value, "evaluated_at": row.evaluated_at.isoformat(),
    }  # fmt: skip


def quote_view(q: ProductQuote) -> dict:
    return {
        "quote_id": str(q.id), "quantity": q.quantity, "currency": q.currency, "unit_amount_minor": q.unit_amount_minor,
        "shipping_amount_minor": q.shipping_amount_minor, "tax_amount_minor": q.tax_amount_minor,
        "total_amount_minor": q.total_amount_minor, "expires_at": q.expires_at.isoformat(), "product": q.quote_snapshot.get("product"),
    }  # fmt: skip


def session_view(s: Session, ps: PurchaseSession) -> dict:
    quote = s.scalars(select(ProductQuote).where(ProductQuote.id.in_(select(PolicyEvaluation.quote_id).where(PolicyEvaluation.purchase_session_id == ps.id)))).first()
    evs = evaluations_for(s, ps.id)
    return {
        "purchase_session_id": str(ps.id), "status": ps.status, "proposed_by": ps.proposed_by,
        "quote": quote_view(quote) if quote else None, "evaluation": evaluation_view(evs[0]) if evs else None,
    }  # fmt: skip
