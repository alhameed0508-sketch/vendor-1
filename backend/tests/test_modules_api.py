"""/api/v1/modules and /api/v1/command-center: counts come from real services and zeros are shown as zeros."""

import pytest
from api.deps import get_alert_service, get_detection_service, get_escalation_service
from core.config import get_settings
from httpx import ASGITransport, AsyncClient


class FakeAlerts:
    def __init__(self, alerts):
        self._alerts = alerts

    def list_alerts(self, severity=None, status=None, limit=50, offset=0):
        return {"total": len(self._alerts), "alerts": self._alerts}


class FakeDetection:
    def __init__(self, source="loaded"):
        self._source = source

    def ensure_alerts(self, skip_demo_statuses=False):
        return []

    def data_source(self):
        return self._source


class FakeEscalations:
    def __init__(self, pending):
        self._pending = pending

    def list_all(self, status=None):
        return [{"status": "PENDING"}] * self._pending if status == "PENDING" else []


def _alert(severity, status="OPEN"):
    return {"alert_id": f"A_{severity}_{status}", "severity": severity, "status": status}


@pytest.fixture
def make_app(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    from api.app import app

    def build(alerts, pending=0, source="loaded"):
        app.dependency_overrides[get_alert_service] = lambda: FakeAlerts(alerts)
        app.dependency_overrides[get_detection_service] = lambda: FakeDetection(source)
        app.dependency_overrides[get_escalation_service] = lambda: FakeEscalations(pending)
        return app

    yield build
    for dep in (get_alert_service, get_detection_service, get_escalation_service):
        app.dependency_overrides.pop(dep, None)
    get_settings.cache_clear()


async def _get(app, path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
async def test_modules_endpoint_lists_every_module_with_derived_status(make_app):
    res = await _get(make_app([]), "/api/v1/modules")
    assert res.status_code == 200
    modules = {m["module_id"]: m for m in res.json()["data"]["modules"]}
    assert set(modules) == {"mule", "upi", "transaction_aml", "identity", "loan"}
    assert modules["loan"]["status"] == "PLANNED"
    assert all({"name", "note", "status"} <= set(c) for c in modules["upi"]["capabilities"])


@pytest.mark.asyncio
async def test_module_detail_and_unknown_module(make_app):
    app = make_app([])
    assert (await _get(app, "/api/v1/modules/mule")).status_code == 200
    assert (await _get(app, "/api/v1/modules/nope")).status_code == 404


@pytest.mark.asyncio
async def test_command_center_counts_match_the_alert_service(make_app):
    alerts = [_alert("CRITICAL"), _alert("HIGH"), _alert("HIGH", "UNDER_REVIEW"), _alert("MEDIUM", "RESOLVED")]
    res = await _get(make_app(alerts, pending=2), "/api/v1/command-center")
    data = res.json()["data"]
    assert data["alerts"]["total"] == 4
    assert data["alerts"]["by_severity"] == {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 1}
    assert data["alerts"]["by_status"] == {"OPEN": 2, "UNDER_REVIEW": 1, "RESOLVED": 1}
    assert data["escalations"]["pending"] == 2


@pytest.mark.asyncio
async def test_command_center_with_zero_alerts_returns_zeros_not_an_error(make_app):
    res = await _get(make_app([]), "/api/v1/command-center")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["alerts"] == {"total": 0, "by_severity": {}, "by_status": {}}
    assert data["escalations"]["pending"] == 0


@pytest.mark.asyncio
async def test_only_the_mule_module_reports_findings_others_report_none(make_app):
    res = await _get(make_app([_alert("HIGH")]), "/api/v1/command-center")
    findings = {m["module_id"]: m["findings"] for m in res.json()["data"]["modules"]}
    assert findings["mule"] == 1
    assert all(v is None for k, v in findings.items() if k != "mule")


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["synthetic", "loaded", "none"])
async def test_command_center_reports_where_the_data_came_from(make_app, source):
    res = await _get(make_app([], source=source), "/api/v1/command-center")
    assert res.json()["data"]["data_source"] == source
