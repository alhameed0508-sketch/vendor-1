"""API contract tests for per-payment real-time scoring."""

import pytest
from api.deps import get_realtime_scorer
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from services.realtime_scorer import RealtimeScorer

PAYMENT = {
    "txn_id": "T-1",
    "from_account": "ACC_A",
    "to_account": "ACC_B",
    "amount": 4500.0,
    "timestamp": "2026-11-02T10:00:00",
}


@pytest.fixture()
def score_app(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()

    from api.app import app

    scorer = RealtimeScorer([], [])
    app.dependency_overrides[get_realtime_scorer] = lambda: scorer
    yield app
    app.dependency_overrides.pop(get_realtime_scorer, None)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_score_returns_decision(score_app):
    async with AsyncClient(transport=ASGITransport(app=score_app), base_url="http://test") as client:
        resp = await client.post("/api/v1/score", json=PAYMENT)

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["txn_id"] == "T-1"
    assert data["decision"] in {"FLAG", "PASS"}
    assert data["action"] == ("route_to_human_review" if data["decision"] == "FLAG" else "none")
    assert "latency_ms" in data


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        {**PAYMENT, "amount": -5},
        {**PAYMENT, "amount": 0},
        {**PAYMENT, "txn_id": ""},
        {k: v for k, v in PAYMENT.items() if k != "to_account"},
        {**PAYMENT, "timestamp": "not-a-date"},
    ],
)
async def test_score_rejects_invalid_payment(score_app, bad):
    async with AsyncClient(transport=ASGITransport(app=score_app), base_url="http://test") as client:
        resp = await client.post("/api/v1/score", json=bad)
    assert resp.status_code in {400, 422}


@pytest.mark.asyncio
async def test_score_endpoint_does_not_write_shared_history(score_app):
    scorer = score_app.dependency_overrides[get_realtime_scorer]()
    async with AsyncClient(transport=ASGITransport(app=score_app), base_url="http://test") as client:
        await client.post("/api/v1/score", json=PAYMENT)
    assert scorer.history_size == 0
