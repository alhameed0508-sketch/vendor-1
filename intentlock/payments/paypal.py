"""PayPal adapter: OAuth client credentials, Orders v2 create / retrieve / capture, webhook verification.

The backend is the only caller. Secrets and access tokens are never logged.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Mapping

import httpx

from intentlock.money import to_major, to_minor
from intentlock.payments.base import (
    CaptureInfo,
    OrderLine,
    OrderRequest,
    OrderSnapshot,
    ProviderRejected,
    ProviderUnavailable,
)

logger = logging.getLogger("intentlock.paypal")
TOKEN_REFRESH_MARGIN_S = 60
WEBHOOK_HEADERS = {
    "auth_algo": "paypal-auth-algo",
    "cert_url": "paypal-cert-url",
    "transmission_id": "paypal-transmission-id",
    "transmission_sig": "paypal-transmission-sig",
    "transmission_time": "paypal-transmission-time",
}


def _money(minor: int, currency: str) -> dict:
    return {"currency_code": currency, "value": to_major(minor, currency)}


def parse_order(body: dict) -> OrderSnapshot:
    """Normalise an Orders v2 response. Raises ValueError if the fields we verify are absent."""
    units = body.get("purchase_units") or []
    if not units:
        raise ValueError("PayPal order has no purchase units")
    first = units[0]
    amount = first["amount"]
    currency = amount["currency_code"]
    payee = first.get("payee") or {}
    items = tuple(
        OrderLine(sku=i.get("sku"), quantity=int(i["quantity"]), unit_amount_minor=to_minor(i["unit_amount"]["value"], i["unit_amount"]["currency_code"]))
        for i in first.get("items") or []
    )
    captures = tuple(
        CaptureInfo(capture_id=c["id"], status=c.get("status", ""), amount_minor=to_minor(c["amount"]["value"], c["amount"]["currency_code"]),
                    currency=c["amount"]["currency_code"], created_at=c.get("create_time"))  # fmt: skip
        for u in units
        for c in (u.get("payments") or {}).get("captures") or []
    )
    return OrderSnapshot(
        order_id=body["id"],
        status=body.get("status", ""),
        currency=currency,
        total_minor=to_minor(amount["value"], currency),
        payee_merchant_id=payee.get("merchant_id"),
        payee_email=payee.get("email_address"),
        purchase_unit_count=len(units),
        items=items,
        custom_id=first.get("custom_id"),
        reference_id=first.get("reference_id"),
        captures=captures,
    )


class PayPalProvider:
    name = "paypal"

    def __init__(self, base_url: str, client_id: str, client_secret: str, *, brand_name: str = "Netrava IntentLock",
                 transport: httpx.BaseTransport | None = None, timeout_s: float = 20.0) -> None:  # fmt: skip
        self._client_id, self._client_secret, self._brand = client_id, client_secret, brand_name
        self._http = httpx.Client(base_url=base_url, timeout=httpx.Timeout(timeout_s, connect=8.0), transport=transport)
        self._token: str | None = None
        self._token_expiry = 0.0
        self._lock = threading.Lock()

    # ── OAuth ────────────────────────────────────────────────────────────────
    def _access_token(self) -> str:
        with self._lock:
            if self._token and time.monotonic() < self._token_expiry - TOKEN_REFRESH_MARGIN_S:
                return self._token
            try:
                r = self._http.post("/v1/oauth2/token", auth=(self._client_id, self._client_secret),
                                    data={"grant_type": "client_credentials"}, headers={"Accept": "application/json"})  # fmt: skip
            except httpx.HTTPError as exc:
                raise ProviderUnavailable(f"PayPal token request failed: {type(exc).__name__}") from exc
            if r.status_code >= 500:
                raise ProviderUnavailable(f"PayPal token endpoint returned {r.status_code}")
            if r.status_code != 200:
                raise ProviderRejected(r.status_code, "AUTHENTICATION_FAILURE", "PayPal rejected the client credentials")
            data = r.json()
            self._token = data["access_token"]
            self._token_expiry = time.monotonic() + float(data.get("expires_in", 300))
            return self._token

    def _request(self, method: str, path: str, *, json_body: dict | None = None, content: bytes | None = None,
                 headers: dict | None = None) -> httpx.Response:  # fmt: skip
        for attempt in (1, 2):
            hdrs = {"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json", **(headers or {})}
            try:
                r = self._http.request(method, path, json=json_body, content=content, headers=hdrs)
            except httpx.HTTPError as exc:
                # The request may or may not have reached PayPal. The caller must reconcile.
                raise ProviderUnavailable(f"PayPal {method} {path.split('?')[0]} failed: {type(exc).__name__}") from exc
            if r.status_code == 401 and attempt == 1:
                with self._lock:
                    self._token = None
                continue
            break
        if r.status_code >= 500:
            raise ProviderUnavailable(f"PayPal returned {r.status_code}")
        if r.status_code >= 400:
            try:
                err = r.json()
            except ValueError:
                err = {}
            details = err.get("details") or [{}]
            raise ProviderRejected(r.status_code, err.get("name", "REQUEST_REJECTED"), err.get("message", "PayPal rejected the request"),
                                   issue=details[0].get("issue", ""), debug_id=err.get("debug_id", ""))  # fmt: skip
        return r

    # ── Orders v2 ────────────────────────────────────────────────────────────
    def build_order_body(self, req: OrderRequest) -> dict:
        cur = req.currency
        return {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": req.reference,
                    "custom_id": req.reference,
                    "description": req.title[:127],
                    "amount": {
                        **_money(req.total_amount_minor, cur),
                        "breakdown": {
                            "item_total": _money(req.unit_amount_minor * req.quantity, cur),
                            "shipping": _money(req.shipping_amount_minor, cur),
                            "tax_total": _money(req.tax_amount_minor, cur),
                        },
                    },
                    "items": [
                        {"name": req.title[:127], "sku": req.sku[:127], "quantity": str(req.quantity),
                         "unit_amount": _money(req.unit_amount_minor, cur), "category": "PHYSICAL_GOODS"}  # fmt: skip
                    ],
                }
            ],
            "payment_source": {
                "paypal": {"experience_context": {"brand_name": self._brand, "user_action": "PAY_NOW", "shipping_preference": "NO_SHIPPING"}}
            },
        }

    def create_order(self, request: OrderRequest, request_id: str) -> OrderSnapshot:
        r = self._request("POST", "/v2/checkout/orders", json_body=self.build_order_body(request),
                          headers={"PayPal-Request-Id": request_id, "Prefer": "return=representation"})  # fmt: skip
        return parse_order(r.json())

    def get_order(self, order_id: str) -> OrderSnapshot:
        return parse_order(self._request("GET", f"/v2/checkout/orders/{order_id}").json())

    def capture_order(self, order_id: str, request_id: str) -> OrderSnapshot:
        r = self._request("POST", f"/v2/checkout/orders/{order_id}/capture", content=b"{}",
                          headers={"PayPal-Request-Id": request_id, "Prefer": "return=representation"})  # fmt: skip
        return parse_order(r.json())

    def patch_order_amount(self, order_id: str, request: OrderRequest, reference_id: str) -> None:
        """Demo tool only (Scenario C): change the order total after it was created."""
        cur = request.currency
        amount = {**_money(request.total_amount_minor, cur), "breakdown": {
            "item_total": _money(request.unit_amount_minor * request.quantity, cur),
            "shipping": _money(request.shipping_amount_minor, cur), "tax_total": _money(request.tax_amount_minor, cur)}}  # fmt: skip
        base = f"/purchase_units/@reference_id=='{reference_id}'"
        ops = [
            {"op": "replace", "path": f"{base}/amount", "value": amount},
            {"op": "replace", "path": f"{base}/items", "value": [
                {"name": request.title[:127], "sku": request.sku[:127], "quantity": str(request.quantity),
                 "unit_amount": _money(request.unit_amount_minor, cur), "category": "PHYSICAL_GOODS"}]},  # fmt: skip
        ]
        self._request("PATCH", f"/v2/checkout/orders/{order_id}", json_body=ops)

    # ── Webhooks ─────────────────────────────────────────────────────────────
    def verify_webhook(self, headers: Mapping[str, str], raw_body: bytes, webhook_id: str) -> bool:
        """Ask PayPal to verify the signature. The event is embedded byte-for-byte: re-serialising it can break the signature."""
        lower = {k.lower(): v for k, v in headers.items()}
        fields = {name: lower.get(header, "") for name, header in WEBHOOK_HEADERS.items()}
        if not webhook_id or not all(fields.values()):
            return False
        try:
            event_text = raw_body.decode("utf-8")
            json.loads(event_text)
        except (UnicodeDecodeError, ValueError):
            return False
        fields["webhook_id"] = webhook_id
        head = ",".join(f"{json.dumps(k)}:{json.dumps(v)}" for k, v in fields.items())
        body = ("{" + head + ',"webhook_event":' + event_text + "}").encode("utf-8")
        r = self._request("POST", "/v1/notifications/verify-webhook-signature", content=body)
        return r.json().get("verification_status") == "SUCCESS"

    def close(self) -> None:
        self._http.close()
