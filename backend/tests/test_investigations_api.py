"""/api/v1/investigations: one workflow over alert and complaint cases, simulated interventions labelled."""

import pytest
from api.deps import get_audit_service, get_investigation_service
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from repositories.audit_repository import AuditRepository
from repositories.investigation_repository import InvestigationRepository
from services.audit_service import AuditService
from services.investigation.investigation_service import InvestigationService


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    from api.app import app

    audit = AuditService(AuditRepository())
    svc = InvestigationService(
        InvestigationRepository(), audit, {"alert": lambda i: i.startswith("AL"), "complaint": lambda i: i == "CMP-1"}
    )
    app.dependency_overrides[get_investigation_service] = lambda: svc
    app.dependency_overrides[get_audit_service] = lambda: audit

    async def call(method, path, **kw):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.request(method, f"/api/v1/investigations{path}", **kw)

    yield call
    for dep in (get_investigation_service, get_audit_service):
        app.dependency_overrides.pop(dep, None)
    get_settings.cache_clear()


async def _open(client, source="alert", source_id="AL1"):
    res = await client("POST", "", json={"source": source, "source_id": source_id})
    assert res.status_code == 200, res.text
    return res.json()["data"]


@pytest.mark.asyncio
async def test_open_then_list_and_get(client):
    inv = await _open(client)
    assert inv["status"] == "NEW"
    listed = (await client("GET", "")).json()["data"]["investigations"]
    assert [i["investigation_id"] for i in listed] == [inv["investigation_id"]]
    assert (await client("GET", f"/{inv['investigation_id']}")).json()["data"]["source_id"] == "AL1"


@pytest.mark.asyncio
async def test_complaint_case_uses_the_same_workflow(client):
    assert (await _open(client, "complaint", "CMP-1"))["source"] == "complaint"


@pytest.mark.asyncio
async def test_unknown_case_is_404_duplicate_is_409_bad_source_is_422(client):
    assert (await client("POST", "", json={"source": "alert", "source_id": "ZZ"})).status_code == 404
    await _open(client)
    assert (await client("POST", "", json={"source": "alert", "source_id": "AL1"})).status_code == 409
    assert (await client("POST", "", json={"source": "loan", "source_id": "X"})).status_code in (400, 422)


@pytest.mark.asyncio
async def test_invalid_transition_is_409_and_resolve_without_outcome_is_rejected(client):
    inv = await _open(client)
    path = f"/{inv['investigation_id']}/transition"
    assert (await client("POST", path, json={"to": "RESOLVED", "outcome": "CONFIRMED"})).status_code == 409
    for step in ("UNDER_REVIEW", "INVESTIGATING"):
        assert (await client("POST", path, json={"to": step})).status_code == 200
    assert (await client("POST", path, json={"to": "RESOLVED"})).status_code in (400, 422)
    done = await client("POST", path, json={"to": "RESOLVED", "outcome": "FALSE_POSITIVE", "note": "customer verified"})
    assert done.json()["data"]["outcome"] == "FALSE_POSITIVE"


@pytest.mark.asyncio
async def test_assign(client):
    inv = await _open(client)
    res = await client("POST", f"/{inv['investigation_id']}/assign", json={"assignee": "analyst7"})
    assert res.json()["data"]["assignee"] == "analyst7"


@pytest.mark.asyncio
async def test_intervention_response_says_simulated_and_lands_in_the_audit_log(client):
    inv = await _open(client)
    res = await client("POST", f"/{inv['investigation_id']}/intervention", json={"kind": "HOLD", "account_id": "ACC-7"})
    data = res.json()["data"]
    assert data["simulated"] is True
    assert data["label"] == "SIMULATED: no bank system connected"
    assert (
        await client("POST", f"/{inv['investigation_id']}/intervention", json={"kind": "NUKE", "account_id": "A"})
    ).status_code in (400, 422)
