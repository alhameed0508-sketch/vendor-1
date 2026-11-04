"""Investigations respect institution and office scope; other banks' cases are indistinguishable from missing ones."""

import pytest
from access.seed import demo_directory
from api.deps import get_access_directory, get_audit_service, get_investigation_service
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from middleware.auth import get_current_user
from repositories.audit_repository import AuditRepository
from repositories.investigation_repository import InvestigationRepository
from services.audit_service import AuditService
from services.investigation.investigation_service import InvestigationService

USERS = {
    "inv_a": {"sub": "investigator", "role": "INVESTIGATOR"},  # bank A, branch 1
    "inv_a2": {"sub": "analyst_a2", "role": "INVESTIGATOR"},  # bank A, branch 2
    "inv_a1b": {"sub": "investigator_a1b", "role": "INVESTIGATOR"},  # bank A, branch 1, second person
    "sup_a": {"sub": "supervisor", "role": "SUPERVISOR"},  # bank A, head office
    "inv_b": {"sub": "investigator_b", "role": "INVESTIGATOR"},  # bank B
    "sup_b": {"sub": "supervisor_b", "role": "SUPERVISOR"},  # bank B
    "admin": {"sub": "admin", "role": "ADMIN"},
    "stranger": {"sub": "stranger", "role": "INVESTIGATOR"},
}


@pytest.fixture
def call(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    from api.app import app

    audit = AuditService(AuditRepository())
    svc = InvestigationService(InvestigationRepository(), audit, {"alert": lambda i: True, "complaint": lambda i: True})
    app.dependency_overrides[get_investigation_service] = lambda: svc
    app.dependency_overrides[get_audit_service] = lambda: audit
    app.dependency_overrides[get_access_directory] = demo_directory

    async def do(who, method, path="", **kw):
        app.dependency_overrides[get_current_user] = lambda: USERS[who]
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            return await c.request(method, f"/api/v1/investigations{path}", **kw)

    yield do
    for dep in (get_investigation_service, get_audit_service, get_access_directory, get_current_user):
        app.dependency_overrides.pop(dep, None)
    get_settings.cache_clear()


async def _open(call, who, case="AL1"):
    res = await call(who, "POST", json={"source": "alert", "source_id": case})
    assert res.status_code == 200, res.text
    return res.json()["data"]


async def _move(call, who, inv_id, to, **extra):
    return await call(who, "POST", f"/{inv_id}/transition", json={"to": to, **extra})


@pytest.mark.asyncio
async def test_a_user_with_no_assignment_gets_an_empty_list_not_a_403(call):
    await _open(call, "inv_a")
    res = await call("stranger", "GET")
    assert res.status_code == 200
    assert res.json()["data"]["investigations"] == []


@pytest.mark.asyncio
async def test_another_banks_case_looks_exactly_like_a_missing_one(call):
    real = await _open(call, "inv_a")
    other_bank = await call("inv_b", "GET", f"/{real['investigation_id']}")
    missing = await call("inv_b", "GET", "/INV_DOESNOTEXIST")
    assert other_bank.status_code == missing.status_code == 404

    def shape(res, case_id):
        body = res.json()
        body.pop("timestamp", None)
        return str(body).replace(case_id, "<id>")

    assert shape(other_bank, real["investigation_id"]) == shape(missing, "INV_DOESNOTEXIST")


@pytest.mark.asyncio
async def test_writes_to_another_banks_case_are_also_not_found(call):
    real = await _open(call, "inv_a")
    assert (await _move(call, "sup_b", real["investigation_id"], "UNDER_REVIEW")).status_code == 404
    assigned = await call("sup_b", "POST", f"/{real['investigation_id']}/assign", json={"assignee": "x"})
    assert assigned.status_code == 404


@pytest.mark.asyncio
async def test_the_same_case_can_be_opened_by_two_banks_without_revealing_each_other(call):
    await _open(call, "inv_a", "AL7")
    again = await call("inv_b", "POST", json={"source": "alert", "source_id": "AL7"})
    assert again.status_code == 200
    dup = await call("inv_a", "POST", json={"source": "alert", "source_id": "AL7"})
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_list_shows_only_what_the_caller_may_read(call):
    a1 = await _open(call, "inv_a", "AL1")
    await _open(call, "inv_a2", "AL2")
    await _open(call, "inv_b", "AL3")
    ids = lambda res: {i["source_id"] for i in res.json()["data"]["investigations"]}  # noqa: E731
    assert ids(await call("inv_a", "GET")) == {"AL1"}
    assert ids(await call("sup_a", "GET")) == {"AL1", "AL2"}
    assert ids(await call("sup_b", "GET")) == {"AL3"}
    assert ids(await call("admin", "GET")) == {"AL1", "AL2", "AL3"}
    assert a1["institution_id"] == "A" and a1["office_id"] == "A-BR1"


@pytest.mark.asyncio
async def test_an_investigator_works_their_own_case_but_not_a_colleagues(call):
    mine = await _open(call, "inv_a")
    assert mine["assignee"] == "investigator"
    assert (await _move(call, "inv_a", mine["investigation_id"], "UNDER_REVIEW")).status_code == 200
    colleague = await call("inv_a1b", "GET", f"/{mine['investigation_id']}")
    assert colleague.status_code == 200  # same office: may read
    assert (await _move(call, "inv_a1b", mine["investigation_id"], "INVESTIGATING")).status_code == 403


@pytest.mark.asyncio
async def test_another_office_in_the_same_bank_cannot_even_see_the_case(call):
    mine = await _open(call, "inv_a")
    assert (await call("inv_a2", "GET", f"/{mine['investigation_id']}")).status_code == 404


@pytest.mark.asyncio
async def test_only_a_supervisor_closes_or_assigns(call):
    inv = await _open(call, "inv_a")
    iid = inv["investigation_id"]
    for step in ("UNDER_REVIEW", "INVESTIGATING"):
        assert (await _move(call, "inv_a", iid, step)).status_code == 200
    assert (await _move(call, "inv_a", iid, "RESOLVED", outcome="UNRESOLVED")).status_code == 200
    assert (await _move(call, "inv_a", iid, "CLOSED")).status_code == 403
    assert (await _move(call, "sup_a", iid, "CLOSED")).status_code == 200
    reassigned = await call("inv_a", "POST", f"/{iid}/assign", json={"assignee": "analyst_a2"})
    assert reassigned.status_code == 403


@pytest.mark.asyncio
async def test_a_supervisor_can_assign_within_their_offices_and_the_investigator_then_acts(call):
    inv = await _open(call, "sup_a")
    iid = inv["investigation_id"]
    assert (await call("inv_a", "GET", f"/{iid}")).status_code == 404  # supervisor opened it at head office
    inv_b = await _open(call, "inv_a", "AL5")
    assigned = await call(
        "sup_a", "POST", f"/{inv_b['investigation_id']}/assign", json={"assignee": "investigator_a1b"}
    )
    assert assigned.status_code == 200
    assert (await _move(call, "inv_a1b", inv_b["investigation_id"], "UNDER_REVIEW")).status_code == 200


@pytest.mark.asyncio
async def test_a_user_outside_the_directory_cannot_open_a_case(call):
    res = await call("stranger", "POST", json={"source": "alert", "source_id": "AL1"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_interventions_follow_the_write_rule(call):
    inv = await _open(call, "inv_a")
    iid = inv["investigation_id"]
    body = {"kind": "HOLD", "account_id": "A1"}
    assert (await call("inv_a", "POST", f"/{iid}/intervention", json=body)).status_code == 200
    assert (await call("inv_a1b", "POST", f"/{iid}/intervention", json=body)).status_code == 403
    assert (await call("inv_b", "POST", f"/{iid}/intervention", json=body)).status_code == 404
