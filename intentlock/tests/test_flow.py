"""End-to-end API scenarios against the fake provider (spec sections 15.2 and 15.5)."""

import json

import pytest
from sqlalchemy import select

from intentlock.db.models import MandateVersion, PaymentRecord
from intentlock.payments.base import ProviderRejected, ProviderUnavailable
from intentlock.services import audit
from intentlock.services.mandates import MandateError
from intentlock.tests.conftest import Harness, mandate


def finalize(h: Harness, co: dict, expect=200):
    return h.post(f"/checkout/{co['checkout_id']}/finalize", expect=expect)


# ── Scenario A: valid purchase ───────────────────────────────────────────────
def test_valid_purchase_is_captured_once_and_receipted(h: Harness):
    m, co = h.checkout_with_order()
    assert co["state"] == "PAYPAL_ORDER_CREATED" and co["paypal_order_id"] == "ORDER1"
    order = h.provider.orders["ORDER1"]["request"]
    assert (order.total_amount_minor, order.currency, order.sku) == (98600, "USD", "NB-ASTER-14")  # from the stored quote

    h.provider.approve("ORDER1")
    done = finalize(h, co)
    assert done["state"] == "RECEIPT_CREATED" and done["payment"] == {"capture_id": "CAP1", "status": "COMPLETED", "amount_minor": 98600, "currency": "USD"}
    assert [e["stage"] + ":" + e["decision"] for e in done["evaluations"]] == ["PRE_ORDER:ALLOW", "PRE_CAPTURE:ALLOW"]

    receipt = h.get(f"/receipts/{done['receipt_id']}")
    assert receipt["integrity"] == {"hash_matches": True, "signature_matches": True}
    assert receipt["receipt"]["mandate"]["canonical_hash"] == m["canonical_hash"]
    assert receipt["receipt"]["payment"]["capture_id"] == "CAP1" and receipt["reconciliation"]["status"] == "PENDING"
    actions = [t["action"] for t in receipt["timeline"]]
    for expected in ("MANDATE_CONFIRMED", "POLICY_EVALUATED", "PAYPAL_ORDER_CREATED", "BUYER_APPROVED", "FINAL_VERIFICATION_PASSED", "CAPTURE_REQUESTED", "CAPTURED", "RECEIPT_CREATED"):
        assert expected in actions
    with h.sessions() as s:
        assert audit.verify_chain(s)[0]

    graph = h.get(f"/graph/{m['mandate_id']}")
    assert {"Buyer", "PurchaseMandate", "MandateVersion", "Product", "Merchant", "PolicyEvaluation", "Checkout", "PayPalOrder", "PaymentCapture"} <= {n["kind"] for n in graph["nodes"]}


def test_duplicate_finalize_and_duplicate_order_requests_do_not_duplicate_anything(h: Harness):
    _, co = h.checkout_with_order()
    again = h.post(f"/checkout/{co['checkout_id']}/paypal-order")
    assert again["paypal_order_id"] == "ORDER1" and h.provider.create_calls == 1
    h.provider.approve("ORDER1")
    first, second = finalize(h, co), finalize(h, co)
    assert first["state"] == second["state"] == "RECEIPT_CREATED" and first["receipt_id"] == second["receipt_id"]
    assert h.provider.capture_calls == 1 and h.provider.captures_made == 1
    with h.sessions() as s:
        assert len(s.scalars(select(PaymentRecord)).all()) == 1


# ── Scenario B: policy violation ─────────────────────────────────────────────
@pytest.mark.parametrize(
    "product_id, decision, rule",
    [
        ("NB-ASTER-14-PLUS", "BLOCK", "MAXIMUM_TOTAL"),
        ("NB-NIMBUS-14", "BLOCK", "MAXIMUM_TOTAL"),
        ("NB-VEGA-15", "BLOCK", "APPROVED_SELLER"),
        ("NB-ASTER-14-USED", "BLOCK", "PRODUCT_CONDITION"),
        ("NB-LUMEN-13", "BLOCK", "SPEC_RAM_GB_MIN"),
        ("NB-KITE-14", "REVIEW", "SPEC_STORAGE_GB_MIN"),
        ("NB-TERRA-14", "REVIEW", "MAXIMUM_TOTAL"),
        ("HP-ECHO-ANC", "BLOCK", "PRODUCT_CATEGORY"),
    ],
)
def test_proposal_outside_the_mandate_never_reaches_paypal(h: Harness, product_id, decision, rule):
    m = h.confirmed_mandate()
    ps = h.post("/purchases/evaluate", {"mandate_id": m["mandate_id"], "product_id": product_id})
    assert ps["evaluation"]["decision"] == decision and rule in ps["evaluation"]["failed_constraints"]
    err = h.post("/checkout", {"purchase_session_id": ps["purchase_session_id"]}, expect=409)
    assert err["code"] == "POLICY_NOT_ALLOWED" and h.provider.create_calls == 0


def test_unconfirmed_mandate_cannot_be_used(h: Harness):
    m = h.post("/intents", {"mandate": mandate()})
    assert h.post("/purchases/evaluate", {"mandate_id": m["mandate_id"], "product_id": "NB-ASTER-14"}, expect=409)["code"] == "MANDATE_NOT_CONFIRMED"


# ── Scenario C: the order changes after approval ─────────────────────────────
@pytest.mark.parametrize(
    "tamper, state, rule",
    [
        ({"unit_amount_minor": 99900, "total_amount_minor": 108600}, "REAUTHORISATION_REQUIRED", "ORDER_AMOUNT"),
        ({"currency": "EUR"}, "REAUTHORISATION_REQUIRED", "ORDER_CURRENCY"),
        ({"payee": "ANOTHER_MERCHANT"}, "BLOCKED", "PAYEE"),
        ({"sku": "NB-ORION-14"}, "REAUTHORISATION_REQUIRED", "ORDER_ITEMS"),
        ({"units": 2}, "REAUTHORISATION_REQUIRED", "ORDER_ITEMS"),
    ],
)
def test_changed_order_is_not_captured(h: Harness, tamper, state, rule):
    _, co = h.checkout_with_order()
    h.provider.approve("ORDER1")
    h.provider.tamper("ORDER1", **tamper)
    out = finalize(h, co)
    assert out["state"] == state and out["payment"] is None and out["receipt_id"] is None
    assert rule in out["evaluations"][-1]["failed_constraints"] and out["evaluations"][-1]["stage"] == "PRE_CAPTURE"
    assert h.provider.capture_calls == 0 and "CAPTURE_REFUSED" in [t["action"] for t in out["timeline"]]
    assert finalize(h, co)["state"] == state and h.provider.capture_calls == 0  # stays refused


def test_browser_claim_of_approval_is_not_trusted(h: Harness):
    _, co = h.checkout_with_order()
    out = finalize(h, co)  # the buyer has not approved in PayPal
    assert out["state"] == "PAYPAL_ORDER_CREATED" and "has not approved" in out["reason"] and h.provider.capture_calls == 0


def test_unverifiable_order_fails_closed(h: Harness):
    _, co = h.checkout_with_order()
    h.provider.approve("ORDER1")
    h.provider.fail_get = ProviderUnavailable("timeout")
    assert finalize(h, co, expect=503)["code"] == "VERIFICATION_UNAVAILABLE" and h.provider.capture_calls == 0
    h.provider.fail_get = None
    assert finalize(h, co)["state"] == "RECEIPT_CREATED"


def test_mandate_changed_or_revoked_after_order_blocks_capture(h: Harness):
    m, co = h.checkout_with_order()
    h.provider.approve("ORDER1")
    v2 = h.client.put(f"/api/v1/intents/{m['mandate_id']}", json={"mandate": mandate(spending__maximum_total_minor=50000)}).json()["data"]
    assert v2["version"] == 2 and v2["status"] == "DRAFT"
    out = finalize(h, co)
    assert out["state"] == "BLOCKED" and "MANDATE_ACTIVE" in out["evaluations"][-1]["failed_constraints"] and h.provider.capture_calls == 0

    m2, co2 = h.checkout_with_order()
    h.provider.approve("ORDER2")
    h.post(f"/intents/{m2['mandate_id']}/revoke")
    assert finalize(h, co2)["state"] == "BLOCKED" and h.provider.capture_calls == 0


# ── capture outcomes ─────────────────────────────────────────────────────────
def test_lost_capture_response_is_reconciled_not_repeated(h: Harness):
    _, co = h.checkout_with_order()
    h.provider.approve("ORDER1")
    h.provider.fail_capture, h.provider.capture_happens_despite_error = ProviderUnavailable("read timeout"), True
    out = finalize(h, co)
    assert out["state"] == "RECONCILIATION_REQUIRED" and out["payment"] is None
    out = finalize(h, co)  # asks PayPal what happened first
    assert out["state"] == "RECEIPT_CREATED" and out["payment"]["capture_id"] == "CAP1"
    assert h.provider.capture_calls == 1 and h.provider.captures_made == 1


def test_capture_that_never_happened_is_retried_with_the_same_request_id(h: Harness):
    _, co = h.checkout_with_order()
    h.provider.approve("ORDER1")
    h.provider.fail_capture = ProviderUnavailable("connect timeout")
    assert finalize(h, co)["state"] == "RECONCILIATION_REQUIRED" and h.provider.captures_made == 0
    assert finalize(h, co)["state"] == "RECEIPT_CREATED" and h.provider.captures_made == 1


def test_declined_capture_is_recorded_as_denied(h: Harness):
    _, co = h.checkout_with_order()
    h.provider.approve("ORDER1")
    h.provider.fail_capture = ProviderRejected(422, "UNPROCESSABLE_ENTITY", "declined", issue="INSTRUMENT_DECLINED")
    out = finalize(h, co)
    assert out["state"] == "CAPTURE_DENIED" and "INSTRUMENT_DECLINED" in out["reason"] and out["receipt_id"] is None


# ── mandate integrity and access ─────────────────────────────────────────────
def test_confirmed_version_is_immutable_and_changes_need_reconfirmation(h: Harness):
    m = h.confirmed_mandate()
    changed = h.client.put(f"/api/v1/intents/{m['mandate_id']}", json={"mandate": mandate(spending__maximum_total_minor=200000)}).json()["data"]
    assert changed["version"] == 2 and changed["status"] == "DRAFT" and changed["canonical_hash"] != m["canonical_hash"]
    with h.sessions() as s:
        v1 = s.scalars(select(MandateVersion).where(MandateVersion.version == 1)).one()
        assert v1.canonical_hash == m["canonical_hash"] and v1.structured_mandate["spending"]["maximum_total_minor"] == 100000
        v1.structured_mandate = {**v1.structured_mandate, "currency": "EUR"}
        with pytest.raises(MandateError):
            s.commit()


def test_confirmation_requires_the_hash_the_buyer_saw(h: Harness):
    m = h.post("/intents", {"mandate": mandate()})
    assert h.post(f"/intents/{m['mandate_id']}/confirm", {"canonical_hash": "0" * 64}, expect=409)["code"] == "MANDATE_CHANGED"


def test_invalid_mandates_are_rejected(h: Harness):
    for bad in (mandate(currency="EUR"), mandate(expires_at="2020-01-01T00:00:00Z")):
        assert h.client.post("/api/v1/intents", json={"mandate": bad}).status_code == 422
    for bad in (mandate(spending__maximum_total_minor=0), mandate(product__quantity=0), mandate(seller__approved_seller_ids=[]), mandate(currency="ZZZ")):
        r = h.client.post("/api/v1/intents", json={"mandate": bad})
        assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = h.client.post("/api/v1/intents", content=json.dumps({"mandate": {**mandate(), "spending": {"maximum_total_minor": 1000.5, "include_shipping": True, "include_tax": True}}}),
                      headers={"content-type": "application/json"})  # fmt: skip
    assert r.status_code == 422


def test_another_buyer_cannot_see_or_use_my_records(h: Harness):
    m, co = h.checkout_with_order()
    other = h.new_client()
    assert h.get(f"/intents/{m['mandate_id']}", client=other, expect=404)["code"] == "NOT_FOUND"
    assert h.get(f"/checkout/{co['checkout_id']}", client=other, expect=404)["code"] == "NOT_FOUND"
    assert h.post(f"/checkout/{co['checkout_id']}/finalize", client=other, expect=404)["code"] == "NOT_FOUND"


def test_write_calls_need_the_client_header_and_health_hides_secrets(h: Harness):
    from fastapi.testclient import TestClient

    bare = TestClient(h.app)
    assert bare.post("/api/v1/intents", json={"mandate": mandate()}).json()["error"]["code"] == "MISSING_CLIENT_HEADER"
    health = bare.get("/health").json()
    assert health["status"] == "ok" and health["database_kind"] == "sqlite" and "test-secret" not in json.dumps(health)
    assert "test-secret" not in json.dumps(bare.get("/api/v1/config").json())
