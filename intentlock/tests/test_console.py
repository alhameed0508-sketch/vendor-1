"""Merchant console: store-wide figures, the ledger, the rule register and the buyer's own lists."""

import json
from datetime import datetime, timedelta, timezone

from intentlock.domain import MandateSpec, MandateState, OfferFacts, QuoteFacts
from intentlock.policy.engine import RULES, evaluate, rule_key
from intentlock.tests.conftest import Harness, mandate

PRIVATE_REQUEST = "A new laptop, 16GB RAM, 512GB, under $1000 all in"  # text used by Harness.confirmed_mandate


def seed(h: Harness) -> dict:
    """One captured purchase, two refusals before the order, and one refusal at the final check."""
    _, co = h.checkout_with_order()
    h.provider.approve(co["paypal_order_id"])
    done = h.post(f"/checkout/{co['checkout_id']}/finalize")
    m = h.confirmed_mandate()
    for product_id in ("NB-ORION-14", "NB-VEGA-15"):
        h.post("/purchases/evaluate", {"mandate_id": m["mandate_id"], "product_id": product_id})
    _, co2 = h.checkout_with_order()
    h.provider.approve(co2["paypal_order_id"])
    h.provider.tamper(co2["paypal_order_id"], unit_amount_minor=99900, total_amount_minor=108600)
    h.post(f"/checkout/{co2['checkout_id']}/finalize")
    return done


def test_overview_reconciles_proposals_to_captures(h: Harness):
    seed(h)
    o = h.get("/console/overview?days=14")
    st = o["statement"]
    assert (st["checked"], st["stopped"], st["allowed"], st["captured"], st["captured_minor"]) == (4, 3, 1, 1, 98600)
    assert st["stopped_by_decision"] == {"BLOCK": 2, "REAUTHORISE": 1, "REVIEW": 0} and st["stopped_at_final_check"] == 1
    assert st["stopped_value_minor"] == 141800 + 93200 + 98600  # Orion, Vega, and the tampered order's approved quote
    assert (st["ordered"], st["approved"]) == (2, 2)
    assert st["refused_rules_by_decision"] == {"BLOCK": 2, "REAUTHORISE": 0, "REVIEW": 0}
    assert (st["refused_rules"], st["refused_rules_value_minor"], st["refused_final"], st["refused_final_value_minor"]) == (2, 141800 + 93200, 1, 98600)
    rules = {r["rule_id"]: r for r in o["by_rule"]}
    assert rules["MAXIMUM_TOTAL"]["count"] == 1 and rules["MAXIMUM_TOTAL"]["title"] == "Within budget" and rules["MAXIMUM_TOTAL"]["reason"] == "Total over budget or unknown" and rules["ORDER_AMOUNT"]["count"] == 1
    assert len(o["per_day"]) == 14 and sum(d["ALLOW"] + d["BLOCK"] + d["REAUTHORISE"] + d["REVIEW"] for d in o["per_day"]) == 4
    assert [e["ref"] for e in o["recent"]] == ["IL-0004", "IL-0003", "IL-0002", "IL-0001"]
    assert o["integrity"]["audit_intact"] is True and o["integrity"]["audit_events"] > 10
    assert o["mandates"] == {"total": 3, "confirmed": 3}
    assert h.client.get("/api/v1/console/overview?days=5").status_code == 422


def test_store_wide_rows_hide_other_buyers_text_and_links(h: Harness):
    seed(h)
    other = h.new_client()
    theirs = h.get("/console/ledger", client=other)
    assert theirs["total"] == 4 and not any(r["mine"] for r in theirs["rows"])
    assert all(r["checkout_id"] is None and r["receipt_id"] is None and r["mandate_id"] is None for r in theirs["rows"])
    body = json.dumps(theirs) + json.dumps(h.get("/console/overview", client=other))
    assert PRIVATE_REQUEST not in body and "merchant@example.test" not in body
    mine = h.get("/console/ledger?scope=mine")
    assert mine["total"] == 4 and all(r["mine"] for r in mine["rows"]) and mine["rows"][-1]["receipt_id"]
    assert h.get("/console/ledger?scope=mine", client=other)["total"] == 0


def test_rule_register_covers_every_rule_the_engine_reports(h: Harness):
    seed(h)
    reg = {r["rule_id"]: r for r in h.get("/policy/rules")["rules"]}
    assert reg["MAXIMUM_TOTAL"]["fired"] == 1 and reg["ORDER_AMOUNT"]["fired"] == 1 and reg["QUANTITY"]["fired"] == 0
    now = datetime.now(timezone.utc)
    spec = MandateSpec.model_validate(mandate(product__model="Aster Book 14"))
    offer = OfferFacts(product_id="p", title="t", category="laptop", condition="new", attributes={"ram_gb": 16}, seller_id="SELLER_001", seller_name="s",
                       merchant_checkout_eligible=True, unit_amount_minor=1, currency="USD", shipping_amount_minor=1, tax_amount_minor=1)  # fmt: skip
    quote = QuoteFacts(quote_id="q", product_id="p", quantity=1, currency="USD", unit_amount_minor=1, shipping_amount_minor=1, tax_amount_minor=1,
                       total_amount_minor=3, expires_at=now + timedelta(minutes=5))  # fmt: skip
    ev = evaluate(mandate=spec, state=MandateState(mandate_id="m", version=1, status="CONFIRMED", is_current_version=True), offer=offer, quote=quote, now=now)
    registered = {r[0] for r in RULES}
    assert {rule_key(c.rule_id) for c in ev.checks} <= registered


def test_buyer_lists_show_only_my_records(h: Harness):
    done = seed(h)
    ms = h.get("/mandates")["mandates"]
    assert len(ms) == 3 and all(m["status"] == "CONFIRMED" for m in ms) and ms[-1]["paid"] == 1 and ms[-1]["request"] == PRIVATE_REQUEST
    cos = h.get("/checkouts")["checkouts"]
    assert {c["state"] for c in cos} == {"RECEIPT_CREATED", "REAUTHORISATION_REQUIRED"}
    rcs = h.get("/receipts")["receipts"]
    assert len(rcs) == 1 and rcs[0]["receipt_id"] == done["receipt_id"] and rcs[0]["share_path"].startswith(f"/r/{done['receipt_id']}.")
    other = h.new_client()
    assert h.get("/mandates", client=other)["mandates"] == [] and h.get("/receipts", client=other)["receipts"] == []
