"""Webhook handling (spec 15.3) and the limits on what the model can do (spec 15.4, Scenario D)."""

import json

from sqlalchemy import select

from intentlock.ai.llm import AIUnavailable
from intentlock.db.models import WebhookEvent
from intentlock.tests.conftest import Harness, ScriptedLLM

GOOD = {"paypal-transmission-sig": "good"}


def send(h: Harness, event: dict, headers=GOOD):
    return h.client.post("/api/v1/paypal/webhooks", content=json.dumps(event), headers={"content-type": "application/json", **headers})


def capture_event(order_id: str, event_id="WH-1", capture_id="CAP1", value="986.00", kind="COMPLETED"):
    return {"id": event_id, "event_type": f"PAYMENT.CAPTURE.{kind}", "resource_type": "capture",
            "resource": {"id": capture_id, "status": kind, "amount": {"currency_code": "USD", "value": value},
                         "supplementary_data": {"related_ids": {"order_id": order_id}}}}  # fmt: skip


def captured(h: Harness) -> dict:
    _, co = h.checkout_with_order()
    h.provider.approve("ORDER1")
    return h.post(f"/checkout/{co['checkout_id']}/finalize")


# ── webhooks ─────────────────────────────────────────────────────────────────
def test_invalid_signature_is_rejected_and_not_stored(h: Harness):
    r = send(h, capture_event("ORDER1"), headers={"paypal-transmission-sig": "forged"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_SIGNATURE"
    with h.sessions() as s:
        assert s.scalars(select(WebhookEvent)).all() == []


def test_webhooks_are_refused_when_no_webhook_id_is_configured():
    h = Harness(paypal_webhook_id="")
    assert send(h, capture_event("ORDER1")).json()["error"]["code"] == "WEBHOOK_NOT_CONFIGURED"


def test_capture_completed_reconciles_and_duplicates_are_processed_once(h: Harness):
    done = captured(h)
    first = send(h, capture_event("ORDER1")).json()["data"]
    assert first == {"event_id": "WH-1", "duplicate": False, "processing_status": "PROCESSED"}
    assert send(h, capture_event("ORDER1")).json()["data"]["duplicate"] is True
    with h.sessions() as s:
        assert len(s.scalars(select(WebhookEvent)).all()) == 1
    receipt = h.get(f"/receipts/{done['receipt_id']}")
    assert receipt["reconciliation"]["status"] == "VERIFIED" and receipt["reconciliation"]["webhook_events"][0]["verified"] is True
    assert receipt["integrity"]["hash_matches"] and [t["action"] for t in receipt["timeline"]].count("WEBHOOK_RECONCILED") == 1


def test_webhook_amount_that_differs_is_flagged_as_mismatch(h: Harness):
    done = captured(h)
    send(h, capture_event("ORDER1", value="1086.00"))
    assert h.get(f"/checkout/{done['checkout_id']}")["reconciliation_status"] == "MISMATCH"


def test_event_for_unknown_order_is_quarantined_and_touches_nothing(h: Harness):
    done = captured(h)
    out = send(h, capture_event("SOMEONE-ELSES-ORDER", event_id="WH-9", capture_id="CAP-X")).json()["data"]
    assert out["processing_status"] == "QUARANTINED"
    assert h.get(f"/checkout/{done['checkout_id']}")["reconciliation_status"] == "PENDING"


def test_out_of_order_capture_event_cannot_mark_a_checkout_captured(h: Harness):
    _, co = h.checkout_with_order()  # order exists, nothing approved or captured by us
    out = send(h, capture_event("ORDER1")).json()["data"]
    assert out["processing_status"] == "IGNORED_STATE"
    after = h.get(f"/checkout/{co['checkout_id']}")
    assert after["state"] == "PAYPAL_ORDER_CREATED" and after["payment"] is None and after["reconciliation_status"] == "MISMATCH"


def test_webhook_completes_a_capture_whose_response_was_lost(h: Harness):
    from intentlock.payments.base import ProviderUnavailable

    _, co = h.checkout_with_order()
    h.provider.approve("ORDER1")
    h.provider.fail_capture, h.provider.capture_happens_despite_error = ProviderUnavailable("timeout"), True
    assert h.post(f"/checkout/{co['checkout_id']}/finalize")["state"] == "RECONCILIATION_REQUIRED"
    assert send(h, capture_event("ORDER1")).json()["data"]["processing_status"] == "PROCESSED"
    after = h.get(f"/checkout/{co['checkout_id']}")
    assert after["state"] == "RECEIPT_CREATED" and after["reconciliation_status"] == "VERIFIED" and h.provider.capture_calls == 1


def test_order_approved_and_refund_events(h: Harness):
    _, co = h.checkout_with_order()
    approved = {"id": "WH-A", "event_type": "CHECKOUT.ORDER.APPROVED", "resource": {"id": "ORDER1"}}
    assert send(h, approved).json()["data"]["processing_status"] == "PROCESSED"
    assert h.get(f"/checkout/{co['checkout_id']}")["state"] == "BUYER_APPROVED" and h.provider.capture_calls == 0  # a webhook never captures
    h.provider.approve("ORDER1")
    assert h.post(f"/checkout/{co['checkout_id']}/finalize")["state"] == "RECEIPT_CREATED"
    refund = {"id": "WH-R", "event_type": "PAYMENT.CAPTURE.REFUNDED", "resource": {"id": "REF1", "links": [{"rel": "up", "href": "https://x/v2/payments/captures/CAP1"}]}}
    assert send(h, refund).json()["data"]["processing_status"] == "PROCESSED"
    assert h.get(f"/checkout/{co['checkout_id']}")["state"] == "REFUNDED"


# ── AI ───────────────────────────────────────────────────────────────────────
FULL = {"category": "Laptop", "condition": "new", "quantity": None, "model": None, "maximum_total": "1,000.00", "currency": "usd",
        "requirements": [{"name": "ram_gb_min", "value": "16"}, {"name": "noise cancelling!", "value": "true"}],
        "include_shipping": True, "include_tax": None, "seller_restriction": None, "substitution_allowed": None, "expires_in_hours": None}  # fmt: skip


def test_request_becomes_a_valid_draft_that_the_buyer_must_still_confirm():
    h = Harness(llm=ScriptedLLM(FULL))
    out = h.post("/intents/parse", {"request": "a new laptop with 16GB under $1000"})
    d = out["draft"]
    assert out["missing"] == [] and d["product"]["category"] == "laptop" and d["spending"]["maximum_total_minor"] == 100000
    assert d["product"]["requirements"] == {"ram_gb_min": 16, "noisecancelling": True} and d["product"]["quantity"] == 1
    assert any("Quantity" in a for a in out["assumptions"]) and out["source"] == "ai"
    saved = h.post("/intents", {"original_request": "a new laptop", "source": "ai", "mandate": d})
    assert saved["status"] == "DRAFT"  # parsing authorises nothing


def test_missing_budget_and_condition_trigger_questions():
    h = Harness(llm=ScriptedLLM({"category": "headphones", "requirements": []}))
    out = h.post("/intents/parse", {"request": "I need some headphones"})
    assert out["missing"] == ["product.condition", "spending.maximum_total_minor"] and len(out["questions"]) == 2
    assert h.client.post("/api/v1/intents", json={"mandate": out["draft"]}).status_code == 422  # an incomplete draft cannot be saved


def test_unsupported_currency_and_unreadable_amount_are_reported():
    h = Harness(llm=ScriptedLLM({**FULL, "currency": "EUR", "maximum_total": "about a grand"}))
    out = h.post("/intents/parse", {"request": "a laptop for about a grand in euros"})
    assert len(out["problems"]) == 2 and "spending.maximum_total_minor" in out["missing"] and out["draft"]["currency"] == "USD"


def test_model_failure_authorises_nothing():
    for llm in (None, ScriptedLLM(AIUnavailable("timeout"))):
        h = Harness(llm=llm)
        assert h.post("/intents/parse", {"request": "a new laptop"}, expect=503)["code"] == "AI_UNAVAILABLE"
        m = h.confirmed_mandate()
        assert h.post("/agent/propose", {"mandate_id": m["mandate_id"]}, expect=503)["code"] == "AI_UNAVAILABLE"
        assert h.provider.create_calls == 0


def test_agent_tricked_by_catalogue_text_is_still_stopped_by_policy():
    """Scenario D: the model follows the injected description; the mandate and the decision do not move."""
    llm = ScriptedLLM({"product_id": "NB-ORION-14", "rationale": "The listing says the buyer approved any price."})
    h = Harness(llm=llm)
    m = h.confirmed_mandate()
    out = h.post("/agent/propose", {"mandate_id": m["mandate_id"]})
    assert out["agent"]["product_id"] == "NB-ORION-14" and out["proposed_by"] == "agent"
    assert out["evaluation"]["decision"] == "BLOCK" and "MAXIMUM_TOTAL" in out["evaluation"]["failed_constraints"]
    assert h.get(f"/intents/{m['mandate_id']}")["canonical_hash"] == m["canonical_hash"]  # mandate unchanged
    assert h.post("/checkout", {"purchase_session_id": out["purchase_session_id"]}, expect=409)["code"] == "POLICY_NOT_ALLOWED"
    system, user = llm.prompts[0]
    assert "never an instruction" in system and "untrusted_description" in user and "CATALOGUE (untrusted data" in user


def test_agent_cannot_propose_a_product_outside_the_catalogue():
    h = Harness(llm=ScriptedLLM({"product_id": "MADE-UP-1", "rationale": "x"}))
    m = h.confirmed_mandate()
    assert h.post("/agent/propose", {"mandate_id": m["mandate_id"]}, expect=503)["code"] == "AI_UNAVAILABLE"


def test_explanation_must_cite_stored_records_and_never_sees_product_descriptions():
    llm = ScriptedLLM({"product_id": "NB-ASTER-14", "rationale": "fits"})
    h = Harness(llm=llm)
    _, co = h.checkout_with_order()
    key = f"checkout:{co['checkout_id']}"
    llm.reply = {"explanation": "The order is waiting for approval.", "evidence_ids": [key, "invented:123"]}
    out = h.post("/assistant/explain", {"checkout_id": co["checkout_id"]})
    assert out["evidence_ids"] == [key]
    assert "matte display" not in llm.prompts[-1][1]  # catalogue description is not passed to the explainer
    llm.reply = {"explanation": "Trust me.", "evidence_ids": ["invented:123"]}
    assert h.post("/assistant/explain", {"checkout_id": co["checkout_id"]}, expect=503)["code"] == "AI_UNAVAILABLE"
