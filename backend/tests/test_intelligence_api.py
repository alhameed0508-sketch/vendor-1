"""GET /api/v1/intelligence/entities/{id}: per-module evidence side by side, links with confidence labels."""

import pytest
from api.deps import get_alert_service, get_detection_service
from core.config import get_settings
from httpx import ASGITransport, AsyncClient


class FakeAlerts:
    def __init__(self, alerts):
        self._alerts = alerts

    def list_alerts(self, severity=None, status=None, limit=50, offset=0):
        return {"total": len(self._alerts), "alerts": self._alerts}


class FakeDetection:
    def __init__(self, dataset):
        self._dataset = dataset

    def ensure_alerts(self, skip_demo_statuses=False):
        return []

    def get_or_generate_dataset(self):
        return self._dataset


def _txn(i, src, dst, device=""):
    return {
        "txn_id": str(i),
        "from_account": src,
        "to_account": dst,
        "amount": 10.0,
        "timestamp": "2026-01-01T10:00:00",
        "channel": "UPI",
        "device_id": device,
    }


MULE_ALERT = {
    "alert_id": "AL1",
    "severity": "HIGH",
    "status": "OPEN",
    "risk_score": 0.87,
    "explanation": "Cluster of 3 accounts",
    "nodes": [{"account_id": "A"}, {"account_id": "B"}],
}
DATASET = {
    "accounts": [
        {"account_id": "A", "cif_id": "C1"},
        {"account_id": "B", "cif_id": "C1"},
        {"account_id": "Z"},
    ],
    "transactions": [_txn(1, "A", "Z", "D1"), _txn(2, "B", "Z", "D1")],
}


@pytest.fixture
def get(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    from api.app import app

    async def call(path, alerts=(MULE_ALERT,), dataset=DATASET):
        app.dependency_overrides[get_alert_service] = lambda: FakeAlerts(list(alerts))
        app.dependency_overrides[get_detection_service] = lambda: FakeDetection(dataset)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path)

    yield call
    for dep in (get_alert_service, get_detection_service):
        app.dependency_overrides.pop(dep, None)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_entity_shows_each_modules_evidence_side_by_side_without_a_combined_score(get):
    res = await get("/api/v1/intelligence/entities/A")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["entity"] == {"kind": "account", "entity_id": "A"}
    modules = {m["module_id"]: m for m in data["modules"]}
    assert set(modules) == {"mule", "upi"}
    assert modules["mule"]["score"] == pytest.approx(0.87)
    assert modules["upi"]["score"] is None
    assert any(e.startswith("R18") for e in modules["upi"]["evidence"])
    assert not {"score", "combined_score", "risk_score"} & set(data)


@pytest.mark.asyncio
async def test_links_carry_a_confidence_label_and_basis(get):
    data = (await get("/api/v1/intelligence/entities/A")).json()["data"]
    by_other = {link["other"]["entity_id"]: link for link in data["links"]}
    assert by_other["B"]["confidence"] == "VERIFIED"
    assert "CIF_ID" in by_other["B"]["basis"]


@pytest.mark.asyncio
async def test_known_account_with_no_findings_returns_empty_modules(get):
    res = await get("/api/v1/intelligence/entities/Z", alerts=())
    assert res.status_code == 200
    assert res.json()["data"]["modules"] == []


@pytest.mark.asyncio
async def test_unknown_entity_is_not_found(get):
    assert (await get("/api/v1/intelligence/entities/NOPE")).status_code == 404
