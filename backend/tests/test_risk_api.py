"""API contract tests for the unified risk engine (/api/v1/risk). No network, no background traffic."""

import pytest
import pytest_asyncio
from api.deps import get_audit_service, get_risk_demo_traffic, get_risk_engine, get_threat_feeds
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from intelligence.engine import UnifiedRiskEngine
from intelligence.threat_feeds import ThreatFeeds

from infra.security.auth import create_access_token

EVENT = {
    "txn_id": "API-1",
    "from_account": "C1",
    "to_account": "SHOP",
    "amount": 450.0,
    "timestamp": "2026-11-02T10:00:00+05:30",
    "session": {"session_id": "S1", "device_id": "PHONE-1", "ip": "10.0.0.1", "city": "Pune"},
    "context": {"channel": "UPI_PUSH"},
}


class FakeAudit:
    def __init__(self):
        self.entries = []

    def log(self, action, user, alert_id=None, details=""):
        self.entries.append({"action": action, "user": user, "details": details})
        return self.entries[-1]


def _auth(role):
    return {"Authorization": f"Bearer {create_access_token(role.lower(), role)}"}


@pytest.fixture()
def env(monkeypatch):
    def apply(auth=False, environment="development"):
        monkeypatch.setenv("ENV", environment)
        monkeypatch.setenv("AUTH_ENABLED", "true" if auth else "false")
        monkeypatch.setenv("JWT_SECRET", "test_secret_key_for_testing_only_32chars")
        get_settings.cache_clear()

    apply()
    yield apply
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def ctx(env):
    from api.app import app

    engine, audit = UnifiedRiskEngine(), FakeAudit()
    app.dependency_overrides[get_risk_engine] = lambda: engine
    app.dependency_overrides[get_risk_demo_traffic] = lambda: None
    app.dependency_overrides[get_threat_feeds] = lambda: ThreatFeeds(enabled=False)
    app.dependency_overrides[get_audit_service] = lambda: audit
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, engine, audit
    for dep in (get_risk_engine, get_risk_demo_traffic, get_threat_feeds, get_audit_service):
        app.dependency_overrides.pop(dep, None)


@pytest.mark.asyncio
async def test_assess_is_a_what_if_with_full_explanation(ctx):
    client, engine, _ = ctx
    resp = await client.post("/api/v1/risk/assess", json=EVENT)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["band"] in ("APPROVE", "STEP_UP", "REVIEW")
    assert data["committed"] is False and data["source"] == "api"
    assert "engines" in data["explanation"]
    assert engine.profiles.customer("C1") is None or engine.profiles.customer("C1").n_payments == 0


@pytest.mark.asyncio
async def test_events_commit_idempotently_and_conflict_on_changed_content(ctx):
    client, engine, _ = ctx
    first = await client.post("/api/v1/risk/events", json=EVENT)
    again = await client.post("/api/v1/risk/events", json=EVENT)
    changed = await client.post("/api/v1/risk/events", json={**EVENT, "amount": 9_999})
    assert first.status_code == 200 and first.json()["data"]["committed"] is True
    assert again.json()["data"]["decision_id"] == first.json()["data"]["decision_id"]
    assert changed.status_code == 409
    assert engine.profiles.customer("C1").n_payments == 1


@pytest.mark.asyncio
async def test_invalid_payment_is_rejected(ctx):
    client, _, _ = ctx
    assert (await client.post("/api/v1/risk/assess", json={**EVENT, "timestamp": "yesterday"})).status_code == 422
    assert (await client.post("/api/v1/risk/assess", json={**EVENT, "amount": -1})).status_code == 422
    resp = await client.post("/api/v1/risk/assess", json={**EVENT, "to_account": "C1"})
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_decisions_list_detail_and_filters(ctx):
    client, _, _ = ctx
    made = (await client.post("/api/v1/risk/events", json=EVENT)).json()["data"]
    listing = (await client.get("/api/v1/risk/decisions", params={"source": "ingest"})).json()["data"]
    assert [d["decision_id"] for d in listing["decisions"]] == [made["decision_id"]]
    assert "explanation" not in listing["decisions"][0]
    detail = await client.get(f"/api/v1/risk/decisions/{made['decision_id']}")
    assert detail.status_code == 200 and "explanation" in detail.json()["data"]
    assert (await client.get("/api/v1/risk/decisions/nope")).status_code == 404
    assert (await client.get("/api/v1/risk/decisions", params={"band": "MAYBE"})).status_code == 422


@pytest.mark.asyncio
async def test_feedback_is_audited_and_updates_the_decision(ctx):
    client, engine, audit = ctx
    made = (await client.post("/api/v1/risk/events", json=EVENT)).json()["data"]
    resp = await client.post(
        f"/api/v1/risk/decisions/{made['decision_id']}/feedback",
        json={"outcome": "FALSE_ALERT", "note": "customer confirmed"},
    )
    assert resp.status_code == 200 and resp.json()["data"]["outcome"] == "FALSE_ALERT"
    assert audit.entries and audit.entries[0]["action"] == "RISK_DECISION_FEEDBACK"
    assert made["decision_id"] in audit.entries[0]["details"]
    bad = await client.post(f"/api/v1/risk/decisions/{made['decision_id']}/feedback", json={"outcome": "MAYBE"})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_metrics_config_feeds_and_scenarios(ctx):
    client, _, _ = ctx
    await client.post("/api/v1/risk/events", json=EVENT)
    metrics = (await client.get("/api/v1/risk/metrics")).json()["data"]
    assert metrics["bands_order"][0] == "APPROVE" and metrics["demo_traffic"] is None
    config = (await client.get("/api/v1/risk/config")).json()["data"]
    assert config["config"]["automatic_decline"] is False
    feeds = (await client.get("/api/v1/risk/feeds")).json()["data"]
    assert {f["name"] for f in feeds["threat_feeds"]["feeds"]} == {"tor_exit", "spamhaus_drop"}
    assert feeds["threat_feeds"]["enabled"] is False
    names = [s["name"] for s in (await client.get("/api/v1/risk/scenarios")).json()["data"]["scenarios"]]
    assert "customer_a_vs_b" in names
    run = (await client.post("/api/v1/risk/scenarios/app_scam_mule_payee/run")).json()["data"]
    assert run["matched_expectation"] is True
    assert (await client.post("/api/v1/risk/scenarios/unknown/run")).status_code == 404


@pytest.mark.asyncio
async def test_demo_stream_refuses_when_demo_traffic_is_off(ctx):
    client, _, _ = ctx
    resp = await client.get("/api/v1/risk/stream", params={"source": "demo"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_roles_guard_ingest_and_feedback(ctx, env):
    client, _, _ = ctx
    env(auth=True)
    guest, investigator, admin = _auth("GUEST"), _auth("INVESTIGATOR"), _auth("ADMIN")
    assert (await client.post("/api/v1/risk/events", json=EVENT, headers=investigator)).status_code == 403
    made = await client.post("/api/v1/risk/events", json=EVENT, headers=admin)
    assert made.status_code == 200
    decision_id = made.json()["data"]["decision_id"]
    assert (await client.post("/api/v1/risk/assess", json=EVENT, headers=guest)).status_code == 403
    assert (
        await client.post(
            f"/api/v1/risk/decisions/{decision_id}/feedback", json={"outcome": "FALSE_ALERT"}, headers=guest
        )
    ).status_code == 403
    assert (await client.get("/api/v1/risk/decisions", headers=guest)).status_code == 200
    assert (await client.get("/api/v1/risk/decisions")).status_code == 401


@pytest.mark.asyncio
async def test_guests_are_refused_outside_the_demo(ctx, env):
    client, _, _ = ctx
    env(auth=True, environment="production")
    assert (await client.get("/api/v1/risk/decisions", headers=_auth("GUEST"))).status_code == 401
