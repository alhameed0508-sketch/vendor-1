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
    def __init__(self, source="loaded", dataset=None):
        self._source = source
        self._dataset = dataset or {"accounts": [], "transactions": []}

    def get_or_generate_dataset(self):
        return self._dataset

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

    def build(alerts, pending=0, source="loaded", dataset=None):
        app.dependency_overrides[get_alert_service] = lambda: FakeAlerts(alerts)
        app.dependency_overrides[get_detection_service] = lambda: FakeDetection(source, dataset)
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
async def test_planned_loan_module_reports_no_findings_and_others_report_a_count(make_app):
    res = await _get(make_app([_alert("HIGH")]), "/api/v1/command-center")
    by_id = {m["module_id"]: m for m in res.json()["data"]["modules"]}
    assert by_id["mule"]["findings"] == 1
    assert by_id["loan"]["findings"] is None
    assert all(by_id[k]["findings"] == 0 for k in ("upi", "transaction_aml", "identity"))


def _txn(i, src, dst, device="D1"):
    return {
        "txn_id": str(i),
        "from_account": src,
        "to_account": dst,
        "amount": 10.0,
        "timestamp": "2026-01-01T10:00:00",
        "channel": "UPI",
        "device_id": device,
    }


@pytest.mark.asyncio
async def test_upi_findings_come_from_the_shared_rule_engine_on_the_loaded_dataset(make_app):
    dataset = {
        "accounts": [{"account_id": a} for a in "ABC"],
        "transactions": [_txn(1, "A", "C"), _txn(2, "B", "C")],
    }
    res = await _get(make_app([], dataset=dataset), "/api/v1/command-center")
    upi = {m["module_id"]: m for m in res.json()["data"]["modules"]}["upi"]
    assert upi["findings"] == 2
    assert [s["rule_code"] for s in upi["skipped_signals"]] == ["R15"]


@pytest.mark.asyncio
async def test_data_without_device_or_handle_lists_the_signals_that_could_not_run(make_app):
    dataset = {"accounts": [{"account_id": "A"}], "transactions": [{**_txn(1, "A", "B"), "device_id": ""}]}
    res = await _get(make_app([], dataset=dataset), "/api/v1/command-center")
    upi = {m["module_id"]: m for m in res.json()["data"]["modules"]}["upi"]
    assert {s["rule_code"] for s in upi["skipped_signals"]} == {"R15", "R18"}
    assert upi["findings"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["synthetic", "loaded", "none"])
async def test_command_center_reports_where_the_data_came_from(make_app, source):
    res = await _get(make_app([], source=source), "/api/v1/command-center")
    assert res.json()["data"]["data_source"] == source


def _payment(i, src, dst, amount, channel="UPI", day=1):
    return {
        "txn_id": f"T{i}",
        "from_account": src,
        "to_account": dst,
        "amount": amount,
        "timestamp": f"2026-09-{day:02d}T10:{i % 60:02d}:00",
        "channel": channel,
    }


@pytest.mark.asyncio
async def test_module_findings_for_the_mule_module_rank_alerts_by_risk(make_app):
    alerts = [
        {
            "alert_id": "A1",
            "severity": "HIGH",
            "status": "OPEN",
            "risk_score": 0.7,
            "account_count": 4,
            "total_amount": 1000.0,
            "reason_codes": ["CC01: Dense cluster"],
        },
        {
            "alert_id": "A2",
            "severity": "CRITICAL",
            "status": "OPEN",
            "risk_score": 0.95,
            "account_count": 6,
            "total_amount": 5000.0,
            "reason_codes": ["RC05: Rapid consolidation", "R05: Fan-in"],
        },
    ]
    app = make_app(alerts)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        data = (await c.get("/api/v1/modules/mule/findings")).json()["data"]
    assert data["kind"] == "alerts" and data["findings_total"] == 2
    assert [a["alert_id"] for a in data["top_alerts"]] == ["A2", "A1"]
    assert data["top_alerts"][0]["reasons"] == ["RC05", "R05"]
    assert data["alerts"]["by_severity"] == {"HIGH": 1, "CRITICAL": 1}
    assert data["accounts_in_alerts"] == 10


@pytest.mark.asyncio
async def test_module_findings_for_a_rule_module_break_down_by_rule(make_app):
    loop = [
        _payment(1, "A", "B", 100_000, "NEFT"),
        _payment(2, "B", "C", 97_000, "NEFT"),
        _payment(3, "C", "A", 95_000, "NEFT"),
    ]
    app = make_app([], dataset={"accounts": [], "transactions": loop})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        data = (await c.get("/api/v1/modules/transaction_aml/findings")).json()["data"]
    assert data["kind"] == "rules"
    cf01 = next(r for r in data["by_rule"] if r["rule_code"] == "CF01")
    assert cf01["accounts"] == 3 and cf01["label"] == "Circular fund flow"
    assert data["accounts_flagged"] >= 3 and "CF01" in data["signals_run"]


@pytest.mark.asyncio
async def test_module_findings_for_loan_say_there_is_no_source(make_app):
    app = make_app([])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        data = (await c.get("/api/v1/modules/loan/findings")).json()["data"]
        missing = await c.get("/api/v1/modules/nope/findings")
    assert data["kind"] == "none" and data["findings_total"] is None
    assert missing.status_code == 404
