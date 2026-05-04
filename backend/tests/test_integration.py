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
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ── Health & Root ─────────────────────────────────────────────────────────────

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "MuleCatch API"
    assert data["status"] == "operational"


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "persistence" in data


# ── Auth endpoints ────────────────────────────────────────────────────────────

def test_auth_me_demo_mode(client):
    """In demo mode (AUTH_ENABLED=false), /auth/me should return default user"""
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert "user_id" in data
    assert "role" in data


def test_auth_login(client):
    r = client.post("/api/auth/login", json={"username": "investigator", "password": "iob@2024"})
    assert r.status_code == 200
    data = r.json()
    assert "token" in data


def test_auth_login_bad_credentials(client):
    r = client.post("/api/auth/login", json={"username": "bad", "password": "bad"})
    assert r.status_code == 401


# ── Alerts ────────────────────────────────────────────────────────────────────

def test_list_alerts(client):
    r = client.get("/api/alerts")
    assert r.status_code == 200
    data = r.json()
    assert "alerts" in data
    assert "total" in data
    assert data["total"] > 0


def test_list_alerts_filtered(client):
    r = client.get("/api/alerts?severity=CRITICAL&limit=5")
    assert r.status_code == 200
    data = r.json()
    for a in data["alerts"]:
        assert a["severity"] == "CRITICAL"


def test_get_single_alert(client):
    # Get first alert from the list
    r = client.get("/api/alerts?limit=1")
    alerts = r.json()["alerts"]
    assert len(alerts) > 0
    alert_id = alerts[0]["alert_id"]

    r = client.get(f"/api/alerts/{alert_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["alert_id"] == alert_id
    assert "risk_score" in data
    assert "reason_codes" in data


def test_get_alert_not_found(client):
    r = client.get("/api/alerts/NONEXISTENT_ALERT")
    assert r.status_code == 404


def test_update_alert(client):
    r = client.get("/api/alerts?limit=1")
    alert_id = r.json()["alerts"][0]["alert_id"]

    r = client.patch(f"/api/alerts/{alert_id}", json={
        "status": "UNDER_REVIEW",
        "investigator_notes": "Integration test note",
    })
    assert r.status_code == 200


def test_get_subgraph(client):
    r = client.get("/api/alerts?limit=1")
    alert_id = r.json()["alerts"][0]["alert_id"]

    r = client.get(f"/api/alerts/{alert_id}/subgraph")
    assert r.status_code == 200
    data = r.json()
    assert "nodes" in data
    assert "edges" in data


# ── Feedback ──────────────────────────────────────────────────────────────────

def test_submit_feedback(client):
    r = client.get("/api/alerts?limit=1")
    alert_id = r.json()["alerts"][0]["alert_id"]

    r = client.post("/api/feedback", json={
        "alert_id": alert_id,
        "is_true_positive": False,
        "notes": "Integration test — false alarm",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["accepted"] is True
    assert "feedback_id" in data


def test_feedback_stats(client):
    r = client.get("/api/feedback/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total_feedback" in data
    assert "false_positive_rate" in data
    assert "current_smurf_threshold" in data


# ── KPI ───────────────────────────────────────────────────────────────────────

def test_kpi(client):
    r = client.get("/api/kpi")
    assert r.status_code == 200
    data = r.json()
    assert "total_alerts" in data
    assert "fraud_prevented_crore" in data
    assert "manpower_saved_lakh" in data


# ── Compliance ────────────────────────────────────────────────────────────────

def test_str_export(client):
    r = client.get("/api/alerts?limit=1")
    alert_id = r.json()["alerts"][0]["alert_id"]

    r = client.post("/api/compliance/str-export", json={"alert_ids": [alert_id]})
    assert r.status_code == 200
    data = r.json()
    assert data["generated"] == 1
    assert len(data["str_reports"]) == 1
    report = data["str_reports"][0]
    assert report["fiu_format_version"] == "2.1"
    assert report["reporting_entity"] == "Indian Overseas Bank"


# ── Graph & Detection ─────────────────────────────────────────────────────────

def test_graph_stats(client):
    r = client.get("/api/graph/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total_accounts" in data
    assert "total_alerts" in data
    assert data["total_accounts"] > 0


def test_run_detection(client):
    r = client.post("/api/run-detection")
    assert r.status_code == 200
    data = r.json()
    assert "message" in data


# ── Ingest Status ─────────────────────────────────────────────────────────────

def test_ingest_status(client):
    r = client.get("/api/ingest/status")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "kafka_enabled" in data


# ── Full flow test ────────────────────────────────────────────────────────────

def test_full_detection_to_str_flow(client):
    """End-to-end: trigger detection -> get alerts -> submit feedback -> export STR"""
    # 1. Trigger detection
    r = client.post("/api/run-detection")
    assert r.status_code == 200

    # 2. List alerts
    r = client.get("/api/alerts")
    assert r.status_code == 200
    alerts = r.json()["alerts"]
    assert len(alerts) > 0

    alert_id = alerts[0]["alert_id"]

    # 3. View alert detail
    r = client.get(f"/api/alerts/{alert_id}")
    assert r.status_code == 200

    # 4. Submit feedback
    r = client.post("/api/feedback", json={
        "alert_id": alert_id,
        "is_true_positive": True,
        "notes": "Confirmed mule cluster",
    })
    assert r.status_code == 200

    # 5. Export STR
    r = client.post("/api/compliance/str-export", json={"alert_ids": [alert_id]})
    assert r.status_code == 200
    assert r.json()["generated"] == 1

    # 6. Check KPIs updated
    r = client.get("/api/kpi")
    assert r.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
