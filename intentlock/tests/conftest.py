"""Test fixtures: an in-memory database, a fake payment provider that behaves like PayPal, and a scripted model."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from intentlock.api import routes
from intentlock.app import create_app
from intentlock.db.session import make_engine
from intentlock.payments.base import CaptureInfo, OrderLine, OrderRequest, OrderSnapshot, ProviderRejected
from intentlock.settings import Settings

MERCHANT = "MERCHANT123"


class FakeProvider:
    """In-memory stand-in for PayPal Orders v2, including idempotent request ids."""

    name = "paypal"

    def __init__(self) -> None:
        self.orders: dict[str, dict] = {}
        self.by_request: dict[str, str] = {}
        self.create_calls = self.capture_calls = self.captures_made = 0
        self.fail_get: Exception | None = None
        self.fail_capture: Exception | None = None
        self.capture_happens_despite_error = False
        self.capture_status = "COMPLETED"

    def _snap(self, oid: str) -> OrderSnapshot:
        o = self.orders[oid]
        r: OrderRequest = o["request"]
        return OrderSnapshot(order_id=oid, status=o["status"], currency=r.currency, total_minor=r.total_amount_minor, payee_merchant_id=o["payee"],
                             payee_email="merchant@example.test", purchase_unit_count=o["units"],
                             items=(OrderLine(sku=r.sku, quantity=r.quantity, unit_amount_minor=r.unit_amount_minor),), custom_id=o["custom_id"],
                             reference_id=r.reference, captures=tuple(o["captures"]))  # fmt: skip

    def create_order(self, request: OrderRequest, request_id: str) -> OrderSnapshot:
        if request_id in self.by_request:
            return self._snap(self.by_request[request_id])
        self.create_calls += 1
        oid = f"ORDER{len(self.orders) + 1}"
        self.orders[oid] = {"status": "PAYER_ACTION_REQUIRED", "request": request, "payee": MERCHANT, "units": 1, "custom_id": request.reference, "captures": []}
        self.by_request[request_id] = oid
        return self._snap(oid)

    def get_order(self, order_id: str) -> OrderSnapshot:
        if self.fail_get:
            raise self.fail_get
        return self._snap(order_id)

    def _do_capture(self, order_id: str) -> None:
        o = self.orders[order_id]
        if not o["captures"]:
            self.captures_made += 1
            r = o["request"]
            o["captures"].append(CaptureInfo(capture_id=f"CAP{self.captures_made}", status=self.capture_status, amount_minor=r.total_amount_minor, currency=r.currency))
            o["status"] = "COMPLETED"

    def capture_order(self, order_id: str, request_id: str) -> OrderSnapshot:
        self.capture_calls += 1
        o = self.orders[order_id]
        if self.fail_capture:
            exc, self.fail_capture = self.fail_capture, None
            if self.capture_happens_despite_error:
                self._do_capture(order_id)
            raise exc
        if o["status"] != "APPROVED" and not o["captures"]:
            raise ProviderRejected(422, "UNPROCESSABLE_ENTITY", "not approved", issue="ORDER_NOT_APPROVED")
        self._do_capture(order_id)
        return self._snap(order_id)

    def verify_webhook(self, headers, raw_body, webhook_id) -> bool:
        return {k.lower(): v for k, v in headers.items()}.get("paypal-transmission-sig") == "good"

    # test controls
    def approve(self, order_id: str) -> None:
        self.orders[order_id]["status"] = "APPROVED"

    def tamper(self, order_id: str, **changes) -> None:
        o = self.orders[order_id]
        fields = {k: v for k, v in changes.items() if k in {f.name for f in dataclasses.fields(OrderRequest)}}
        o["request"] = dataclasses.replace(o["request"], **fields)
        for key in ("payee", "units", "custom_id"):
            if key in changes:
                o[key] = changes[key]


class ScriptedLLM:
    model = "scripted-test-model"

    def __init__(self, reply: dict | Exception) -> None:
        self.reply, self.prompts = reply, []

    def generate_json(self, system: str, user: str, schema: dict) -> dict:
        self.prompts.append((system, user))
        reply = self.reply.pop(0) if isinstance(self.reply, list) else self.reply  # a list is played back in order
        if isinstance(reply, Exception):
            raise reply
        return reply


def settings(**overrides) -> Settings:
    base = dict(paypal_client_id="test-id", paypal_client_secret="test-secret", paypal_webhook_id="WH-TEST", database_url="sqlite://",
                session_secret="s" * 40, genai_enabled=False, genai_api_key="", paypal_merchant_id="")  # fmt: skip
    return Settings(_env_file=None, **{**base, **overrides})


def mandate(**changes) -> dict:
    body = {
        "currency": "USD",
        "product": {"category": "laptop", "condition": "new", "quantity": 1, "model": None, "requirements": {"ram_gb_min": 16, "storage_gb_min": 512}},
        "seller": {"mode": "allowlist", "approved_seller_ids": ["SELLER_001"]},
        "spending": {"maximum_total_minor": 100000, "include_shipping": True, "include_tax": True},
        "substitution": {"allowed": False, "require_reapproval": True},
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    for path, value in changes.items():
        node, keys = body, path.split("__")
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = value
    return body


class Harness:
    def __init__(self, llm=None, **setting_overrides) -> None:
        self.provider = FakeProvider()
        self.settings = settings(**setting_overrides)
        self.app = create_app(self.settings, provider=self.provider, llm=llm, engine=make_engine("sqlite://"), migrate=False)
        self.client = self.new_client()

    def new_client(self) -> TestClient:
        return TestClient(self.app, headers={"X-IntentLock-Client": "test"})

    def sessions(self):
        return self.app.state.container.sessions()

    def post(self, path: str, json=None, client=None, expect=200):
        r = (client or self.client).post(f"/api/v1{path}", json=json or {})
        assert r.status_code == expect, r.text
        return r.json()["data"] if expect == 200 else r.json()["error"]

    def get(self, path: str, client=None, expect=200):
        r = (client or self.client).get(f"/api/v1{path}")
        assert r.status_code == expect, r.text
        return r.json()["data"] if expect == 200 else r.json()["error"]

    def confirmed_mandate(self, **changes) -> dict:
        m = self.post("/intents", {"original_request": "A new laptop, 16GB RAM, 512GB, under $1000 all in", "source": "manual", "mandate": mandate(**changes)})
        return self.post(f"/intents/{m['mandate_id']}/confirm", {"canonical_hash": m["canonical_hash"]})

    def checkout_with_order(self, product_id: str = "NB-ASTER-14", **changes) -> tuple[dict, dict]:
        m = self.confirmed_mandate(**changes)
        ps = self.post("/purchases/evaluate", {"mandate_id": m["mandate_id"], "product_id": product_id})
        assert ps["evaluation"]["decision"] == "ALLOW", ps["evaluation"]["failed_constraints"]
        co = self.post("/checkout", {"purchase_session_id": ps["purchase_session_id"]})
        co = self.post(f"/checkout/{co['checkout_id']}/paypal-order")
        return m, co


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    routes._hits.clear()
    yield


@pytest.fixture
def h() -> Harness:
    return Harness()
