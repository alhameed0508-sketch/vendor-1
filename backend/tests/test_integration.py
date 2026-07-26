"""
MuleCatch API Integration Tests
================================
Tests all API endpoints sequentially to verify end-to-end flow.
Run: python -m pytest backend/tests/test_integration.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from api.app import app


_detection_seeded = False


@pytest_asyncio.fixture
async def client():
    global _detection_seeded
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Seed detection once per module — other test modules may clear alert state
        if not _detection_seeded:
            await c.post("/api/v1/run-detection")
            _detection_seeded = True
        yield c


def _data(response):
    """Extract 'data' from envelope response."""
    body = response.json()
    assert body["success"] is True, f"Expected success=True, got: {body}"
    return body["data"]


def _error(response):
    """Extract 'error' from envelope response."""
    body = response.json()
    assert body["success"] is False
    return body["error"]


# ── Health & Root ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_root(client):
    r = await client.get("/")
    assert r.status_code == 200
    data = _data(r)
    assert data["service"] == "MuleCatch API"
    assert data["status"] == "operational"


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = _data(r)
    assert data["status"] == "ok"
    assert "persistence" in data


# ── Auth endpoints ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_auth_me_demo_mode(client):
    """In demo mode (AUTH_ENABLED=false), /auth/me should return default user"""
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200
    data = _data(r)
    assert "user_id" in data
    assert "role" in data


@pytest.mark.asyncio
async def test_auth_login(client):
    r = await client.post("/api/v1/auth/login", json={"username": "investigator", "password": "iob@2024"})
    # Accept 429 (rate limited by earlier test_auth_api.py rate limit tests)
    assert r.status_code in (200, 429)
    if r.status_code == 200:
        data = _data(r)
        assert "access_token" in data


@pytest.mark.asyncio
async def test_auth_login_bad_credentials(client):
    r = await client.post("/api/v1/auth/login", json={"username": "bad", "password": "bad"})
    # Accept 429 (rate limited by earlier tests)
    assert r.status_code in (401, 429)


# ── Alerts ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_alerts(client):
    r = await client.get("/api/v1/alerts")
    assert r.status_code == 200
    data = _data(r)
    assert "alerts" in data
    assert "total" in data
    assert data["total"] > 0


@pytest.mark.asyncio
async def test_list_alerts_filtered(client):
    r = await client.get("/api/v1/alerts?severity=CRITICAL&limit=5")
    assert r.status_code == 200
    data = _data(r)
    for a in data["alerts"]:
        assert a["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_get_single_alert(client):
    # Get first alert from the list
    r = await client.get("/api/v1/alerts?limit=1")
    alerts = _data(r)["alerts"]
    assert len(alerts) > 0
    alert_id = alerts[0]["alert_id"]

    r = await client.get(f"/api/v1/alerts/{alert_id}")
    assert r.status_code == 200
    data = _data(r)
    assert data["alert_id"] == alert_id
    assert "risk_score" in data
    assert "reason_codes" in data


@pytest.mark.asyncio
async def test_get_alert_not_found(client):
    r = await client.get("/api/v1/alerts/NONEXISTENT_ALERT")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_alert(client):
    r = await client.get("/api/v1/alerts?limit=1")
    alert_id = _data(r)["alerts"][0]["alert_id"]

    r = await client.patch(f"/api/v1/alerts/{alert_id}", json={
        "status": "UNDER_REVIEW",
        "investigator_notes": "Integration test note",
    })
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_get_subgraph(client):
    r = await client.get("/api/v1/alerts?limit=1")
    alert_id = _data(r)["alerts"][0]["alert_id"]

    r = await client.get(f"/api/v1/alerts/{alert_id}/subgraph")
    assert r.status_code == 200
    data = _data(r)
    assert "nodes" in data
    assert "edges" in data


# ── Feedback ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_feedback(client):
    r = await client.get("/api/v1/alerts?limit=1")
    alert_id = _data(r)["alerts"][0]["alert_id"]

    r = await client.post("/api/v1/feedback", json={
        "alert_id": alert_id,
        "is_true_positive": False,
        "notes": "Integration test — false alarm",
    })
    assert r.status_code == 200
    data = _data(r)
    assert data["accepted"] is True
    assert "feedback_id" in data


@pytest.mark.asyncio
async def test_feedback_stats(client):
    r = await client.get("/api/v1/feedback/stats")
    assert r.status_code == 200
    data = _data(r)
    assert "total_feedback" in data
    assert "false_positive_rate" in data
    assert "current_smurf_threshold" in data


# ── KPI ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_kpi(client):
    r = await client.get("/api/v1/kpi")
    assert r.status_code == 200
    data = _data(r)
    assert "total_alerts" in data
    assert "fraud_prevented_crore" in data
    assert "manpower_saved_lakh" in data


# ── Compliance ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_str_export(client):
    r = await client.get("/api/v1/alerts?limit=1")
    alert_id = _data(r)["alerts"][0]["alert_id"]

    r = await client.post("/api/v1/compliance/str-export", json={"alert_ids": [alert_id]})
    assert r.status_code == 200
    data = _data(r)
    assert data["generated"] == 1
    assert len(data["str_reports"]) == 1
    report = data["str_reports"][0]
    assert report["fiu_format_version"] == "2.1"
    assert report["reporting_entity"] == "Indian Overseas Bank"


# ── Graph & Detection ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_graph_stats(client):
    r = await client.get("/api/v1/graph/stats")
    assert r.status_code == 200
    data = _data(r)
    assert "total_accounts" in data
    assert "total_alerts" in data
    assert data["total_accounts"] > 0


@pytest.mark.asyncio
async def test_run_detection(client):
    r = await client.post("/api/v1/run-detection")
    # Accept 429 (rate limited — seeded in fixture or by earlier test runs)
    assert r.status_code in (200, 429)
    if r.status_code == 200:
        data = _data(r)
        assert "message" in data


# ── Ingest Status ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_status(client):
    r = await client.get("/api/v1/ingest/status")
    assert r.status_code == 200
    data = _data(r)
    assert "status" in data
    assert "kafka_enabled" in data


# ── Full flow test ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_detection_to_str_flow(client):
    """End-to-end: trigger detection -> get alerts -> submit feedback -> export STR"""
    # 1. Trigger detection (may be rate-limited by prior runs)
    r = await client.post("/api/v1/run-detection")
    assert r.status_code in (200, 429)

    # 2. List alerts
    r = await client.get("/api/v1/alerts")
    assert r.status_code == 200
    alerts = _data(r)["alerts"]
    assert len(alerts) > 0

    alert_id = alerts[0]["alert_id"]

    # 3. View alert detail
    r = await client.get(f"/api/v1/alerts/{alert_id}")
    assert r.status_code == 200

    # 4. Submit feedback
    r = await client.post("/api/v1/feedback", json={
        "alert_id": alert_id,
        "is_true_positive": True,
        "notes": "Confirmed mule cluster",
    })
    assert r.status_code == 200

    # 5. Export STR
    r = await client.post("/api/v1/compliance/str-export", json={"alert_ids": [alert_id]})
    assert r.status_code == 200
    assert _data(r)["generated"] == 1

    # 6. Check KPIs updated
    r = await client.get("/api/v1/kpi")
    assert r.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
