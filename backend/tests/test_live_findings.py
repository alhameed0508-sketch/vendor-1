"""Detection modules on real live payments: the shared buffer, the live feed filling it, and source=live findings."""

import pytest
from api.deps import get_live_buffer
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from services.live_buffer import LiveBuffer
from services.live_feed import LiveFeed


def _event(i, src, dst, amount, decision="PASS", case=None, members=(), reasons=(), ts="2026-11-05T10:00:00+00:00"):
    return {
        "payment": {"txn_id": f"T{i}", "from_account": src, "to_account": dst, "amount": amount, "timestamp": ts},
        "decision": decision,
        "case_id": case,
        "ring_members": list(members),
        "reasons": list(reasons),
    }


def test_buffer_keeps_each_payment_once_and_stays_bounded():
    buf = LiveBuffer(max_payments=3)
    for i in range(5):
        buf.add(_event(i, "A", "B", 10))
    buf.add(_event(4, "A", "B", 10))  # a second viewer sees the same payment
    buf.add({"notice": "quiet"})  # not a payment
    assert [e["payment"]["txn_id"] for e in buf.snapshot()] == ["T2", "T3", "T4"]
    buf.add(_event(0, "A", "B", 10))  # evicted ids can come back
    assert len(buf) == 3 and buf.snapshot()[-1]["payment"]["txn_id"] == "T0"


def test_live_feed_hands_every_event_to_its_sink():
    tx = {
        "txid": "a" * 64,
        "vin": [{"is_coinbase": False, "prevout": {"scriptpubkey_address": "S1", "value": 60_000_000}}],
        "vout": [{"scriptpubkey_address": "R1", "value": 50_000_000}],
        "status": {"confirmed": False},
    }

    class _Client:
        def inr_per_btc(self):
            return 1_000_000.0

        def recent_txids(self):
            return [tx["txid"]]

        def tx(self, txid):
            return tx

    seen = []
    events = list(LiveFeed(_Client(), poll_interval=0, sleep=lambda s: None, sink=seen.append).events(limit=1))
    assert seen == events and seen[0]["payment"]["from_account"] == "S1"


@pytest.fixture
def live_app(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    get_live_buffer.cache_clear()
    from api.app import app

    yield app
    get_live_buffer.cache_clear()
    get_settings.cache_clear()


async def _findings(app, module_id):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/api/v1/modules/{module_id}/findings", params={"source": "live"})
    assert res.status_code == 200
    return res.json()["data"]


@pytest.mark.asyncio
async def test_before_any_live_payment_the_modules_say_they_are_waiting(live_app):
    data = await _findings(live_app, "transaction_aml")
    assert data["data_source"] == "live" and data["live_payments"] == 0
    assert data["findings_total"] == 0 and data["rows_considered"] == 0


@pytest.mark.asyncio
async def test_mule_module_reports_what_the_live_network_scorer_held_by_reason(live_app):
    buf = get_live_buffer()
    buf.add(_event(1, "A", "B", 5_000))
    reasons = ["CC01: Dense transaction cluster (density=0.40)", "RC03: High fan-out"]
    buf.add(_event(2, "M1", "M2", 90_000, "FLAG", "CASE-1", ("M1", "M2", "M3"), reasons))
    buf.add(_event(3, "M2", "M3", 80_000, "FLAG", "CASE-1", ("M1", "M2", "M3"), reasons[:1]))
    data = await _findings(live_app, "mule")
    assert data["kind"] == "rules" and data["data_source"] == "live"
    assert data["findings_total"] == 2 and data["cases"] == 1
    assert data["accounts_flagged"] == 3 and data["rows_considered"] == 3
    assert {r["rule_code"]: r["findings"] for r in data["by_rule"]} == {"CC01": 2, "RC03": 1}
    assert data["by_rule"][0]["label"] == "Dense transaction cluster"
    assert data["findings"][0]["account_id"] == "M2"  # newest first


@pytest.mark.asyncio
async def test_rule_modules_run_on_the_live_payments_and_say_what_they_cannot_check(live_app):
    buf = get_live_buffer()
    loop = [("A", "B", 100_000, "10:00"), ("B", "C", 97_000, "11:00"), ("C", "A", 95_000, "12:00")]
    for i, (src, dst, amount, hhmm) in enumerate(loop):
        buf.add(_event(i, src, dst, amount, ts=f"2026-11-05T{hhmm}:00+00:00"))
    aml = await _findings(live_app, "transaction_aml")
    assert aml["rows_considered"] == 3 and aml["live_payments"] == 3
    assert "CF01" in {r["rule_code"] for r in aml["by_rule"]}
    identity = await _findings(live_app, "identity")
    assert [s["rule_code"] for s in identity["signals_skipped"]] == ["R20"]  # no account ages in public payments
    upi = await _findings(live_app, "upi")
    assert upi["rows_considered"] == 0  # no UPI channel in public payments
    loan = await _findings(live_app, "loan")
    assert loan["kind"] == "none"


@pytest.mark.asyncio
async def test_unknown_findings_source_is_rejected(live_app):
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://test") as client:
        res = await client.get("/api/v1/modules/mule/findings", params={"source": "synthetic"})
    assert res.status_code in {400, 422}


@pytest.mark.asyncio
async def test_api_docs_may_load_their_cdn_bundles_and_nothing_else_may(live_app):
    async with AsyncClient(transport=ASGITransport(app=live_app), base_url="http://test") as client:
        docs = await client.get("/docs")
        api = await client.get("/api/v1/modules")
    assert "https://cdn.jsdelivr.net" in docs.headers["content-security-policy"]
    assert "cdn.jsdelivr.net" not in api.headers["content-security-policy"]
