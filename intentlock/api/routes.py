"""HTTP API. Handlers are thin: validate, check ownership, call a service, return the envelope."""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from intentlock.ai import assistant
from intentlock.ai.llm import LLM
from intentlock.db.models import Buyer, CheckoutSession, MandateVersion, PurchaseMandate, PurchaseReceipt, PurchaseSession
from intentlock.domain import MandateSpec
from intentlock.payments.base import PaymentProvider
from intentlock.policy.engine import POLICY_VERSION
from intentlock.services import activity, agent, catalog, checkout, console, mandates, purchases, receipts, webhooks
from intentlock.settings import Settings

SESSION_COOKIE = "il_buyer"
CLIENT_HEADER = "x-intentlock-client"


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


@dataclass
class Container:
    settings: Settings
    sessions: sessionmaker[Session]
    provider: PaymentProvider
    llm: LLM | None


def ok(data) -> dict:
    return {"success": True, "data": data, "error": None}


# ── dependencies ─────────────────────────────────────────────────────────────
def container(request: Request) -> Container:
    return request.app.state.container


def db(c: Container = Depends(container)):
    s = c.sessions()
    try:
        yield s
    finally:
        s.close()


def _sign(buyer_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), buyer_id.encode(), hashlib.sha256).hexdigest()


def buyer(request: Request, response: Response, s: Session = Depends(db), c: Container = Depends(container)) -> Buyer:
    """The buyer for this browser session. A signed, http-only cookie; created on first use."""
    secret = c.settings.resolved_session_secret
    found = None
    raw = request.cookies.get(SESSION_COOKIE, "")
    if "." in raw:
        buyer_id, sig = raw.split(".", 1)
        if hmac.compare_digest(sig, _sign(buyer_id, secret)):
            try:
                found = s.get(Buyer, uuid.UUID(buyer_id))
            except ValueError:
                found = None
    if found is None:
        found = mandates.get_or_create_buyer(s, None)
        secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        response.set_cookie(SESSION_COOKIE, f"{found.id}.{_sign(str(found.id), secret)}", httponly=True, samesite="lax", secure=secure,
                            max_age=60 * 60 * 24 * 30, path="/")  # fmt: skip
    return found


def csrf(request: Request) -> None:
    """State-changing browser calls must carry a custom header, which a cross-site form cannot send."""
    if not request.headers.get(CLIENT_HEADER):
        raise ApiError(403, "MISSING_CLIENT_HEADER", "This request must come from the IntentLock web app")


_hits: dict[tuple[str, str], deque] = defaultdict(deque)


def limit(name: str, per_minute: int):
    def dep(request: Request) -> None:
        ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()) or (request.client.host if request.client else "unknown")
        q, now = _hits[(name, ip)], time.monotonic()
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= per_minute:
            raise ApiError(429, "RATE_LIMIT_EXCEEDED", "Too many requests. Please wait a moment.")
        q.append(now)

    return dep


def _uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ApiError(404, "NOT_FOUND", f"{what} not found") from exc


def _mandate(s: Session, mandate_id: str, who: Buyer) -> PurchaseMandate:
    m = s.get(PurchaseMandate, _uuid(mandate_id, "Mandate"))
    if m is None or m.buyer_id != who.id:
        raise ApiError(404, "NOT_FOUND", "Mandate not found")
    return m


def _checkout(s: Session, checkout_id: str, who: Buyer) -> CheckoutSession:
    co = s.get(CheckoutSession, _uuid(checkout_id, "Checkout"))
    if co is None or checkout.context(s, co).mandate.buyer_id != who.id:
        raise ApiError(404, "NOT_FOUND", "Checkout not found")
    return co


# ── request bodies ───────────────────────────────────────────────────────────
class ParseBody(BaseModel):
    request: str = Field(min_length=3, max_length=2000)


class IntentBody(BaseModel):
    original_request: str = Field(default="", max_length=4000)
    source: Literal["ai", "manual"] = "manual"
    mandate: MandateSpec


class MandateBody(BaseModel):
    mandate: MandateSpec


class ConfirmBody(BaseModel):
    canonical_hash: str = Field(min_length=64, max_length=64)


class SearchBody(BaseModel):
    mandate_id: str | None = None
    category: str | None = Field(default=None, max_length=60)
    text: str | None = Field(default=None, max_length=200)


class ProposeBody(BaseModel):
    mandate_id: str


class EvaluateBody(BaseModel):
    mandate_id: str
    product_id: str = Field(max_length=120)
    quantity: int | None = Field(default=None, ge=1, le=99)


class CheckoutBody(BaseModel):
    purchase_session_id: str


class ExplainBody(BaseModel):
    checkout_id: str


class AgentRunBody(BaseModel):
    mandate_id: str
    mode: Literal["assistant", "manipulated"] = "assistant"


def _featured_path(st: Settings) -> str | None:
    """FEATURED_RECEIPT may hold a share token, a /r/ path or a full share link. Returns the /r/ path if it is valid."""
    raw = st.featured_receipt.strip()
    if not raw:
        return None
    token = raw.rsplit("/r/", 1)[-1].strip("/")
    return f"/r/{token}" if receipts.receipt_id_from_token(token, st.resolved_receipt_key) else None


def build_router() -> APIRouter:
    r = APIRouter(prefix="/api/v1")
    write = [Depends(csrf)]

    @r.get("/config")
    def config(c: Container = Depends(container), _who: Buyer = Depends(buyer)):
        st = c.settings
        return ok({
            "paypal_client_id": st.paypal_client_id, "paypal_env": st.paypal_env, "currency": st.paypal_currency.upper(),
            "ai_enabled": c.llm is not None, "ai_model": c.llm.model if c.llm else None, "database": st.database_kind,
            "database_durable": st.database_kind == "postgresql", "webhook_configured": bool(st.paypal_webhook_id),
            "policy_version": POLICY_VERSION, "demo_tools": st.demo_tools, "default_seller_ids": ["SELLER_001"],
            "catalogue": "synthetic demo catalogue", "featured_receipt_path": _featured_path(st),
        })  # fmt: skip

    # ── intents ──────────────────────────────────────────────────────────────
    @r.post("/intents/parse", dependencies=[*write, Depends(limit("parse", 20))])
    def parse_intent(body: ParseBody, c: Container = Depends(container), _who: Buyer = Depends(buyer)):
        return ok(assistant.parse_intent(c.llm, body.request, c.settings.paypal_currency.upper(), ["SELLER_001"]))

    @r.post("/intents", dependencies=write)
    def save_intent(body: IntentBody, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        m = mandates.create_draft(s, who, body.original_request, body.mandate, body.source, c.settings.paypal_currency)
        return ok(mandates.view(s, m))

    @r.put("/intents/{mandate_id}", dependencies=write)
    def change_intent(mandate_id: str, body: MandateBody, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        m = mandates.update_draft(s, _mandate(s, mandate_id, who), body.mandate, who, c.settings.paypal_currency)
        return ok(mandates.view(s, m))

    @r.post("/intents/{mandate_id}/confirm", dependencies=write)
    def confirm_intent(mandate_id: str, body: ConfirmBody, s: Session = Depends(db), who: Buyer = Depends(buyer)):
        return ok(mandates.view(s, mandates.confirm(s, _mandate(s, mandate_id, who), who, body.canonical_hash)))

    @r.post("/intents/{mandate_id}/revoke", dependencies=write)
    def revoke_intent(mandate_id: str, s: Session = Depends(db), who: Buyer = Depends(buyer)):
        return ok(mandates.view(s, mandates.revoke(s, _mandate(s, mandate_id, who), who)))

    @r.get("/intents/{mandate_id}")
    def get_intent(mandate_id: str, s: Session = Depends(db), who: Buyer = Depends(buyer)):
        return ok(mandates.view(s, _mandate(s, mandate_id, who)))

    # ── catalogue ────────────────────────────────────────────────────────────
    @r.post("/catalog/search", dependencies=write)
    def search(body: SearchBody, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        m = _mandate(s, body.mandate_id, who) if body.mandate_id else None
        category = body.category or (mandates.spec_of(mandates.current_version(s, m)).product.category if m else None)
        rows = catalog.search(s, category=category, text=body.text)
        out = []
        for p in rows:
            item = catalog.product_view(p)
            if m is not None:
                ev = purchases.preview(s, m, p, c.settings.quote_ttl_minutes)
                item["policy_preview"] = {"decision": ev.decision.value,
                                          "failed": [{"rule_id": ch.rule_id, "status": ch.status.value, "reason": ch.reason} for ch in ev.checks if ch.status.value != "PASS"]}  # fmt: skip
            out.append(item)
        return ok({"category": category, "products": out, "source": "demo_catalogue", "synthetic": True})

    @r.get("/catalog/products/{product_id}")
    def product(product_id: str, s: Session = Depends(db), _who: Buyer = Depends(buyer)):
        p = catalog.get_product(s, product_id)
        if p is None:
            raise ApiError(404, "NOT_FOUND", "Product not found")
        return ok(catalog.product_view(p))

    # ── proposals ────────────────────────────────────────────────────────────
    def _confirmed(s: Session, mandate_id: str, who: Buyer) -> PurchaseMandate:
        m = _mandate(s, mandate_id, who)
        if mandates.current_version(s, m).confirmed_at is None:
            raise ApiError(409, "MANDATE_NOT_CONFIRMED", "Confirm the mandate before choosing a product")
        return m

    @r.post("/purchases/evaluate", dependencies=write)
    def evaluate(body: EvaluateBody, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        m = _confirmed(s, body.mandate_id, who)
        p = catalog.get_product(s, body.product_id)
        if p is None:
            raise ApiError(404, "NOT_FOUND", "Product not found")
        ps = purchases.propose(s, mandate=m, product=p, quantity=body.quantity, proposed_by="buyer", agent_session_ref=None, actor_id=who.id,
                               ttl_minutes=c.settings.quote_ttl_minutes)  # fmt: skip
        return ok(purchases.session_view(s, ps))

    @r.post("/agent/propose", dependencies=[*write, Depends(limit("agent", 20))])
    def agent_propose(body: ProposeBody, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        """The assistant picks a product; the deterministic engine then decides whether it may be bought."""
        m = _confirmed(s, body.mandate_id, who)
        version = mandates.current_version(s, m)
        spec = mandates.spec_of(version)
        rows = catalog.search(s, category=spec.product.category) or catalog.search(s)
        choice = assistant.propose_product(c.llm, version.structured_mandate, [catalog.product_view(p) for p in rows])
        p = catalog.get_product(s, choice["product_id"])
        ref = f"agent-{uuid.uuid4().hex[:12]}"
        ps = purchases.propose(s, mandate=m, product=p, quantity=None, proposed_by="agent", agent_session_ref=ref, actor_id=ref,
                               ttl_minutes=c.settings.quote_ttl_minutes)  # fmt: skip
        return ok({**purchases.session_view(s, ps), "agent": {**choice, "agent_session_ref": ref}})

    @r.post("/agent/run", dependencies=[*write, Depends(limit("agent", 20))])
    def agent_run(body: AgentRunBody, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        """The assistant proposes; a refusal is fed back and it may try again. 'manipulated' starts with a simulated bad pick."""
        m = _confirmed(s, body.mandate_id, who)
        return ok(agent.run(s, llm=c.llm, mandate=m, mode=body.mode, ttl_minutes=c.settings.quote_ttl_minutes))

    @r.get("/activity")
    def get_activity(s: Session = Depends(db), who: Buyer = Depends(buyer)):
        return ok(activity.for_buyer(s, who.id))

    # ── merchant console (store-wide; no typed request text or contact details) ──
    @r.get("/console/overview", dependencies=[Depends(limit("console", 120))])
    def console_overview(days: int = 14, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        if days not in (0, 7, 14, 30):
            raise ApiError(422, "VALIDATION_ERROR", "days must be 7, 14, 30 or 0 for all time")
        return ok(console.overview(s, who.id, days, c.settings.paypal_currency.upper()))

    @r.get("/console/ledger", dependencies=[Depends(limit("console", 120))])
    def console_ledger(scope: Literal["all", "mine"] = "all", s: Session = Depends(db), who: Buyer = Depends(buyer)):
        return ok(console.ledger(s, who.id, mine_only=scope == "mine"))

    @r.get("/policy/rules")
    def policy_rules(s: Session = Depends(db), _who: Buyer = Depends(buyer)):
        return ok({**console.rule_register(s), "policy_version": POLICY_VERSION})

    @r.get("/mandates")
    def list_mandates(s: Session = Depends(db), who: Buyer = Depends(buyer)):
        return ok({"mandates": console.my_mandates(s, who.id)})

    @r.get("/checkouts")
    def list_checkouts(s: Session = Depends(db), who: Buyer = Depends(buyer)):
        return ok({"checkouts": console.my_checkouts(s, who.id)})

    @r.get("/receipts")
    def list_receipts(s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        return ok({"receipts": console.my_receipts(s, who.id, c.settings.resolved_receipt_key)})

    # ── checkout ─────────────────────────────────────────────────────────────
    @r.post("/checkout", dependencies=write)
    def create_checkout(body: CheckoutBody, s: Session = Depends(db), who: Buyer = Depends(buyer)):
        ps = s.get(PurchaseSession, _uuid(body.purchase_session_id, "Proposal"))
        if ps is None or s.get(PurchaseMandate, s.get(MandateVersion, ps.mandate_version_id).mandate_id).buyer_id != who.id:
            raise ApiError(404, "NOT_FOUND", "Proposal not found")
        return ok(checkout.view(s, checkout.create(s, ps, who.id)))

    @r.post("/checkout/{checkout_id}/paypal-order", dependencies=[*write, Depends(limit("order", 30))])
    def paypal_order(checkout_id: str, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        co = _checkout(s, checkout_id, who)
        return ok(checkout.view(s, checkout.create_order(s, co.id, c.provider, c.settings)))

    @r.post("/checkout/{checkout_id}/finalize", dependencies=[*write, Depends(limit("finalize", 30))])
    def finalize(checkout_id: str, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        """The browser supplies only the checkout id. Approval, amount and payee are read from PayPal by the server."""
        co = _checkout(s, checkout_id, who)
        return ok(checkout.view(s, checkout.finalize(s, co.id, c.provider, c.settings)))

    @r.post("/checkout/{checkout_id}/cancel", dependencies=write)
    def cancel(checkout_id: str, s: Session = Depends(db), who: Buyer = Depends(buyer)):
        co = _checkout(s, checkout_id, who)
        return ok(checkout.view(s, checkout.cancel(s, co.id, who.id)))

    @r.get("/checkout/{checkout_id}")
    def get_checkout(checkout_id: str, s: Session = Depends(db), who: Buyer = Depends(buyer)):
        return ok(checkout.view(s, _checkout(s, checkout_id, who)))

    @r.post("/demo/tamper/{checkout_id}", dependencies=write)
    def tamper(checkout_id: str, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        """Demo tool (Scenario C): change the PayPal order total behind the checkout's back. Off unless DEMO_TOOLS=true."""
        if not c.settings.demo_tools or not hasattr(c.provider, "patch_order_amount"):
            raise ApiError(404, "NOT_FOUND", "Not found")
        co = _checkout(s, checkout_id, who)
        if not co.paypal_order_id:
            raise ApiError(409, "ORDER_NOT_CREATED", "No PayPal order exists for this checkout yet")
        ctx = checkout.context(s, co)
        q = ctx.quote
        from intentlock.payments.base import OrderRequest

        bumped = q.unit_amount_minor + 10000
        req = OrderRequest(reference=str(co.id), title=ctx.product.title, sku=ctx.product.provider_product_id, quantity=q.quantity, currency=q.currency,
                           unit_amount_minor=bumped, shipping_amount_minor=q.shipping_amount_minor, tax_amount_minor=q.tax_amount_minor,
                           total_amount_minor=bumped * q.quantity + q.shipping_amount_minor + q.tax_amount_minor)  # fmt: skip
        c.provider.patch_order_amount(co.paypal_order_id, req, str(co.id))
        return ok({"tampered": True, "note": "Demo tool: the PayPal order total was raised outside IntentLock. The stored quote is unchanged."})

    # ── webhooks, receipts, graph, assistant ─────────────────────────────────
    @r.post("/paypal/webhooks", dependencies=[Depends(limit("webhook", 240))])
    async def paypal_webhook(request: Request, c: Container = Depends(container)):
        raw = await request.body()
        with c.sessions() as s:
            return ok(webhooks.handle(s, c.provider, c.settings, dict(request.headers), raw))

    def _receipt(s: Session, receipt_id: str, who: Buyer) -> PurchaseReceipt:
        rc = s.get(PurchaseReceipt, _uuid(receipt_id, "Receipt"))
        if rc is None or checkout.context(s, s.get(CheckoutSession, rc.checkout_session_id)).mandate.buyer_id != who.id:
            raise ApiError(404, "NOT_FOUND", "Receipt not found")
        return rc

    @r.get("/receipts/{receipt_id}")
    def get_receipt(receipt_id: str, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        return ok(receipts.view(s, _receipt(s, receipt_id, who), c.settings.resolved_receipt_key))

    @r.get("/public/receipts/{token}", dependencies=[Depends(limit("public_receipt", 60))])
    def shared_receipt(token: str, c: Container = Depends(container)):
        """Read-only receipt for anyone holding its share link. No session is created and no contact details are returned."""
        key = c.settings.resolved_receipt_key
        receipt_id = receipts.receipt_id_from_token(token, key)
        with c.sessions() as s:
            rc = s.get(PurchaseReceipt, receipt_id) if receipt_id else None
            if rc is None:
                raise ApiError(404, "NOT_FOUND", "This receipt link is not valid")
            return ok(receipts.public_view(s, rc, key))

    @r.get("/graph/{mandate_id}")
    def graph(mandate_id: str, s: Session = Depends(db), who: Buyer = Depends(buyer)):
        return ok(receipts.graph(s, _mandate(s, mandate_id, who)))

    @r.post("/assistant/explain", dependencies=[*write, Depends(limit("explain", 20))])
    def explain(body: ExplainBody, s: Session = Depends(db), who: Buyer = Depends(buyer), c: Container = Depends(container)):
        """Explain a checkout from stored records only. The model gets read-only copies, never product descriptions."""
        v = checkout.view(s, _checkout(s, body.checkout_id, who))
        records = {
            f"mandate:{v['mandate']['mandate_id']}:v{v['mandate']['version']}": mandates.view(s, _mandate(s, v["mandate"]["mandate_id"], who))["mandate"],
            f"product:{v['product']['product_id']}": {k: v["product"][k] for k in ("title", "condition", "attributes", "seller_name")},
            f"quote:{v['quote']['quote_id']}": {k: v["quote"][k] for k in ("quantity", "currency", "unit_amount_minor", "shipping_amount_minor", "tax_amount_minor", "total_amount_minor")},
            f"checkout:{v['checkout_id']}": {"state": v["state"], "reason": v["reason"], "reconciliation": v["reconciliation_status"]},
        }
        for e in v["evaluations"]:
            records[f"evaluation:{e['evaluation_id']}"] = {"stage": e["stage"], "decision": e["decision"],
                                                          "not_passed": [{"rule": ch["rule_id"], "reason": ch["reason"]} for ch in e["checks"] if ch["status"] != "PASS"]}  # fmt: skip
        if v["payment"]:
            records[f"payment:{v['payment']['capture_id']}"] = v["payment"]
        return ok(assistant.explain(c.llm, records))

    return r


def health_payload(c: Container) -> dict:
    st = c.settings
    try:
        with c.sessions() as s:
            s.execute(text("SELECT 1"))
            s.scalar(select(PurchaseMandate.id).limit(1))
        database = "ok"
    except Exception:  # noqa: BLE001
        database = "unavailable"
    return {
        "status": "ok" if database == "ok" else "degraded", "database": database, "database_kind": st.database_kind,
        "database_durable": st.database_kind == "postgresql", "paypal_env": st.paypal_env, "paypal_configured": st.paypal_configured,
        "webhook_configured": bool(st.paypal_webhook_id), "ai_enabled": c.llm is not None, "policy_version": POLICY_VERSION,
    }  # fmt: skip
