"""Policy engine rules (spec section 15.1). Pure function tests, no database."""

from datetime import datetime, timedelta, timezone

import pytest

from intentlock.domain import ExpectedOrder, MandateSpec, MandateState, OfferFacts, OrderFacts, OrderItem, QuoteFacts
from intentlock.policy.engine import evaluate, fail_closed
from intentlock.tests.conftest import mandate

NOW = datetime.now(timezone.utc)


def run(mandate_changes=None, offer=None, quote=None, state=None, order=None, expected=None, now=NOW):
    spec = MandateSpec.model_validate(mandate(**(mandate_changes or {})))
    o = dict(product_id="NB-ASTER-14", title="Aster Book 14", category="laptop", condition="new", attributes={"model": "Aster Book 14", "ram_gb": 16, "storage_gb": 512},
             seller_id="SELLER_001", seller_name="Netrava Demo Store", merchant_checkout_eligible=True, unit_amount_minor=89900, currency="USD",
             shipping_amount_minor=1500, tax_amount_minor=7200)  # fmt: skip
    o.update(offer or {})
    q = dict(quote_id="q1", product_id=o["product_id"], quantity=1, currency="USD", unit_amount_minor=o["unit_amount_minor"],
             shipping_amount_minor=o["shipping_amount_minor"], tax_amount_minor=o["tax_amount_minor"], expires_at=NOW + timedelta(minutes=30))  # fmt: skip
    q["total_amount_minor"] = None if None in (q["shipping_amount_minor"], q["tax_amount_minor"]) else q["unit_amount_minor"] + q["shipping_amount_minor"] + q["tax_amount_minor"]
    q.update(quote or {})
    st = dict(mandate_id="m1", version=1, status="CONFIRMED", is_current_version=True)
    st.update(state or {})
    return evaluate(mandate=spec, state=MandateState(**st), offer=OfferFacts(**o), quote=QuoteFacts(**q), now=now, order=order, expected=expected)


def test_valid_product_within_budget_is_allowed():
    ev = run()
    assert ev.decision.value == "ALLOW" and ev.failed_constraints == [] and not ev.requires_buyer_reapproval


@pytest.mark.parametrize(
    "kwargs, decision, rule",
    [
        ({"offer": {"unit_amount_minor": 114900}}, "BLOCK", "MAXIMUM_TOTAL"),
        ({"offer": {"unit_amount_minor": 94900, "shipping_amount_minor": 2000, "tax_amount_minor": 7600}}, "BLOCK", "MAXIMUM_TOTAL"),
        ({"offer": {"seller_id": "SELLER_207"}}, "BLOCK", "APPROVED_SELLER"),
        ({"offer": {"merchant_checkout_eligible": False}}, "BLOCK", "MERCHANT_CHECKOUT_ELIGIBLE"),
        ({"offer": {"attributes": {"ram_gb": 8, "storage_gb": 512}}}, "BLOCK", "SPEC_RAM_GB_MIN"),
        ({"offer": {"attributes": {"ram_gb": 16}}}, "REVIEW", "SPEC_STORAGE_GB_MIN"),
        ({"offer": {"condition": "used"}}, "BLOCK", "PRODUCT_CONDITION"),
        ({"offer": {"category": "tablet"}}, "BLOCK", "PRODUCT_CATEGORY"),
        ({"quote": {"quantity": 2}, "mandate_changes": {"spending__maximum_total_minor": 300000}}, "REAUTHORISE", "QUANTITY"),
        ({"quote": {"currency": "EUR"}}, "REAUTHORISE", "CURRENCY"),
        ({"offer": {"tax_amount_minor": None}}, "REVIEW", "MAXIMUM_TOTAL"),
        ({"offer": {"shipping_amount_minor": None}}, "REVIEW", "MAXIMUM_TOTAL"),
        ({"state": {"status": "REVOKED"}}, "BLOCK", "MANDATE_ACTIVE"),
        ({"state": {"is_current_version": False}}, "BLOCK", "MANDATE_ACTIVE"),
        ({"now": NOW + timedelta(days=3)}, "BLOCK", "MANDATE_ACTIVE"),
        ({"mandate_changes": {"product__model": "Lumen Air 13"}}, "REAUTHORISE", "SUBSTITUTION"),
        ({"quote": {"expires_at": NOW - timedelta(minutes=1)}}, "REVIEW", "QUOTE_FRESH"),
        ({"offer": {"availability_status": "unknown"}}, "REVIEW", "AVAILABILITY"),
    ],
)
def test_each_rule(kwargs, decision, rule):
    ev = run(**kwargs)
    assert ev.decision.value == decision
    assert rule in ev.failed_constraints


def test_tax_not_counted_when_budget_excludes_it():
    ev = run(mandate_changes={"spending__include_tax": False}, offer={"tax_amount_minor": None})
    assert ev.decision.value == "ALLOW"


def test_substitution_allowed_passes_and_any_seller_passes():
    assert run(mandate_changes={"product__model": "Other", "substitution__allowed": True}).decision.value == "ALLOW"
    changes = {"seller__mode": "any", "seller__approved_seller_ids": []}
    assert run(mandate_changes=changes, offer={"seller_id": "SELLER_207"}).decision.value == "ALLOW"


def test_block_outranks_reauthorise_and_review():
    ev = run(offer={"unit_amount_minor": 200000, "attributes": {"ram_gb": 16}}, quote={"quantity": 2})
    assert ev.decision.value == "BLOCK"
    assert {"MAXIMUM_TOTAL", "QUANTITY", "SPEC_STORAGE_GB_MIN"} <= set(ev.failed_constraints)


def test_every_check_records_expected_observed_source_and_reason():
    for ch in run(offer={"condition": "used"}).checks:
        assert ch.rule_id and ch.expected and ch.observed and ch.source and ch.reason


def _order(**changes):
    base = dict(order_id="O1", status="APPROVED", currency="USD", total_minor=98600, payee_merchant_id="M1", purchase_unit_count=1,
                items=[OrderItem(sku="NB-ASTER-14", quantity=1, unit_amount_minor=89900)], custom_id="co1", has_capture=False)  # fmt: skip
    base.update(changes)
    return OrderFacts(**base)


EXPECTED = ExpectedOrder(order_id="O1", payee_merchant_id="M1", custom_id="co1", sku="NB-ASTER-14")


def test_matching_approved_order_is_allowed_before_capture():
    ev = run(order=_order(), expected=EXPECTED)
    assert ev.stage == "PRE_CAPTURE" and ev.decision.value == "ALLOW"


@pytest.mark.parametrize(
    "changes, decision, rule",
    [
        ({"total_minor": 108600}, "REAUTHORISE", "ORDER_AMOUNT"),
        ({"currency": "EUR"}, "REAUTHORISE", "ORDER_CURRENCY"),
        ({"payee_merchant_id": "SOMEONE_ELSE"}, "BLOCK", "PAYEE"),
        ({"order_id": "O2"}, "BLOCK", "ORDER_ID"),
        ({"status": "PAYER_ACTION_REQUIRED"}, "REVIEW", "ORDER_APPROVED_BY_BUYER"),
        ({"items": [OrderItem(sku="NB-ORION-14", quantity=1, unit_amount_minor=89900)]}, "REAUTHORISE", "ORDER_ITEMS"),
        ({"purchase_unit_count": 2}, "REAUTHORISE", "ORDER_ITEMS"),
        ({"custom_id": "another-checkout"}, "REAUTHORISE", "ORDER_ITEMS"),
        ({"has_capture": True}, "BLOCK", "NOT_ALREADY_CAPTURED"),
    ],
)
def test_order_that_differs_is_not_allowed(changes, decision, rule):
    ev = run(order=_order(**changes), expected=EXPECTED)
    assert ev.decision.value == decision and rule in ev.failed_constraints


def test_unknown_expected_payee_is_review_not_allow():
    ev = run(order=_order(), expected=ExpectedOrder(order_id="O1", custom_id="co1", sku="NB-ASTER-14"))
    assert ev.decision.value == "REVIEW" and "PAYEE" in ev.failed_constraints


def test_engine_failure_never_allows():
    assert fail_closed("PRE_CAPTURE", "boom").decision.value == "REVIEW"
