"""Shared receipt links, agent runs that react to a refusal, and the activity ledger."""

import json

from fastapi.testclient import TestClient

from intentlock.ai.llm import AIUnavailable
from intentlock.tests.conftest import Harness, ScriptedLLM


def captured(h: Harness) -> dict:
    _, co = h.checkout_with_order()
    h.provider.approve(co["paypal_order_id"])
    return h.post(f"/checkout/{co['checkout_id']}/finalize")


# ── shared receipt ───────────────────────────────────────────────────────────
def test_owner_gets_a_share_link_that_anyone_can_open_read_only(h: Harness):
    done = captured(h)
    mine = h.get(f"/receipts/{done['receipt_id']}")
    assert mine["shared"] is False and mine["share_path"].startswith(f"/r/{done['receipt_id']}.")
    stranger = TestClient(h.app)  # no cookie, no client header
    r = stranger.get(f"/api/v1/public/receipts/{mine['share_path'][3:]}")
    assert r.status_code == 200 and "set-cookie" not in r.headers
    shared = r.json()["data"]
    assert shared["shared"] is True and shared["share_path"] is None and shared["integrity"] == {"hash_matches": True, "signature_matches": True}
    assert shared["receipt"]["payment"]["capture_id"] == "CAP1" and shared["receipt_hash"] == mine["receipt_hash"]
    assert shared["receipt"]["payment"]["payee"] == {"merchant_id": "MERCHANT123"} and "merchant@example.test" not in json.dumps(shared)
    assert {n["kind"] for n in shared["graph"]["nodes"]} >= {"PurchaseMandate", "PayPalOrder", "PaymentCapture"}
    assert stranger.get(f"/api/v1/receipts/{done['receipt_id']}").status_code == 404  # the private route still needs the owner


def test_share_link_cannot_be_guessed_from_the_receipt_id(h: Harness):
    done = captured(h)
    stranger = TestClient(h.app)
    for token in (done["receipt_id"], f"{done['receipt_id']}.{'0' * 32}", "not-a-token", f"{done['receipt_id']}."):
        assert stranger.get(f"/api/v1/public/receipts/{token}").json()["error"]["code"] == "NOT_FOUND"


def test_featured_receipt_is_offered_only_when_the_setting_holds_a_valid_link(h: Harness):
    done = captured(h)
    path = h.get(f"/receipts/{done['receipt_id']}")["share_path"]
    assert h.get("/config")["featured_receipt_path"] is None
    h.settings.featured_receipt = f"https://example.test{path}"
    assert h.get("/config")["featured_receipt_path"] == path
    h.settings.featured_receipt = "/r/made-up"
    assert h.get("/config")["featured_receipt_path"] is None


# ── agent run ────────────────────────────────────────────────────────────────
def test_manipulated_agent_is_refused_then_corrects_itself_with_the_engine_feedback():
    llm = ScriptedLLM([{"product_id": "NB-ASTER-14", "rationale": "Meets every requirement within budget."}])
    h = Harness(llm=llm)
    m = h.confirmed_mandate()
    out = h.post("/agent/run", {"mandate_id": m["mandate_id"], "mode": "manipulated"})
    first, second = out["run"]["steps"]
    assert first["simulated"] is True and first["product_id"] == "NB-ORION-14" and first["decision"] == "BLOCK"
    assert "MAXIMUM_TOTAL" in [f["rule_id"] for f in first["failed"]]
    assert second["simulated"] is False and second["product_id"] == "NB-ASTER-14" and second["decision"] == "ALLOW"
    assert out["run"]["outcome"] == "ALLOW" and out["evaluation"]["decision"] == "ALLOW" and out["proposed_by"] == "agent"
    _, user = llm.prompts[0]  # the retry prompt carries the engine's refusal, and no longer offers the refused product
    assert "REFUSED BY THE RULE ENGINE" in user and "MAXIMUM_TOTAL" in user and '"product_id": "NB-ORION-14", "title": "Orion 14 Pro", "untrusted_description"' not in user
    assert h.get(f"/intents/{m['mandate_id']}")["canonical_hash"] == m["canonical_hash"]
    co = h.post("/checkout", {"purchase_session_id": out["purchase_session_id"]})  # only the allowed proposal can be checked out
    assert co["state"] == "POLICY_ALLOWED" and h.post("/checkout", {"purchase_session_id": first["purchase_session_id"]}, expect=409)["code"] == "POLICY_NOT_ALLOWED"


def test_agent_stops_after_three_refusals_and_never_gets_a_checkout():
    replies = [{"product_id": p, "rationale": "x"} for p in ("NB-NIMBUS-14", "NB-VEGA-15", "NB-LUMEN-13")]
    h = Harness(llm=ScriptedLLM(replies))
    m = h.confirmed_mandate()
    out = h.post("/agent/run", {"mandate_id": m["mandate_id"]})
    assert [s["decision"] for s in out["run"]["steps"]] == ["BLOCK", "BLOCK", "BLOCK"] and out["run"]["outcome"] == "BLOCK"
    assert h.post("/checkout", {"purchase_session_id": out["purchase_session_id"]}, expect=409)["code"] == "POLICY_NOT_ALLOWED"
    assert h.provider.create_calls == 0


def test_manipulated_run_without_a_model_shows_the_refusal_and_stops():
    for llm in (None, ScriptedLLM([AIUnavailable("timeout")])):
        h = Harness(llm=llm)
        m = h.confirmed_mandate()
        out = h.post("/agent/run", {"mandate_id": m["mandate_id"], "mode": "manipulated"})
        assert out["run"]["steps"][0]["decision"] == "BLOCK" and out["run"]["steps"][1]["stopped"] is True and out["run"]["outcome"] == "BLOCK"
    assert Harness(llm=None).post("/agent/run", {"mandate_id": Harness(llm=None).confirmed_mandate()["mandate_id"]}, expect=404)["code"] == "NOT_FOUND"
    h = Harness(llm=None)
    assert h.post("/agent/run", {"mandate_id": h.confirmed_mandate()["mandate_id"]}, expect=503)["code"] == "AI_UNAVAILABLE"


# ── activity ─────────────────────────────────────────────────────────────────
def test_activity_lists_proposals_with_decisions_and_payments(h: Harness):
    assert h.get("/activity")["stats"]["proposals"] == 0
    done = captured(h)
    m = h.confirmed_mandate()
    for product_id in ("NB-ORION-14", "NB-VEGA-15"):
        h.post("/purchases/evaluate", {"mandate_id": m["mandate_id"], "product_id": product_id})
    _, co = h.checkout_with_order()
    h.provider.approve(co["paypal_order_id"])
    h.provider.tamper(co["paypal_order_id"], unit_amount_minor=99900, total_amount_minor=108600)
    h.post(f"/checkout/{co['checkout_id']}/finalize")

    a = h.get("/activity")
    st = a["stats"]
    assert (st["proposals"], st["allowed"], st["refused"], st["captured_count"], st["captured_minor"], st["currency"]) == (4, 1, 3, 1, 98600, "USD")
    rules = {r["rule_id"]: r["count"] for r in st["by_rule"]}
    assert rules["MAXIMUM_TOTAL"] == 1 and rules["APPROVED_SELLER"] == 1 and rules["ORDER_AMOUNT"] == 1
    newest, *_, oldest = a["rows"]
    assert newest["outcome"] == "REAUTHORISATION_REQUIRED" and newest["refused_at"] == "PRE_CAPTURE" and newest["decision"] == "REAUTHORISE"
    assert oldest["outcome"] == "RECEIPT_CREATED" and oldest["receipt_id"] == done["receipt_id"] and oldest["capture_id"] == "CAP1"
    assert h.get("/activity", client=h.new_client())["stats"]["proposals"] == 0  # another buyer sees none of it
