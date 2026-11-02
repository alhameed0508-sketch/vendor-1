"""Fraud Complaint Desk API: deadlines, evidence intake, decisions and evidence packs."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio
from api.deps import get_audit_service, get_complaint_service
from complaints.seed import DEMO_NOW
from core.config import get_settings
from httpx import ASGITransport, AsyncClient
from repositories.complaint_repository import ComplaintRepository
from services.complaint_service import ComplaintService

from infra.security.auth import create_access_token

NOW = DEMO_NOW
MULE_ALERT = {"alert_id": "ALT_MULE1", "risk_score": 0.97,
              "nodes": [{"account_id": "AC_MULE_1", "role": "AGGREGATOR"}, {"account_id": "AC_SRC", "role": "SOURCE"}]}


class FakeAlerts:
    def find_all(self, **kwargs):
        return [MULE_ALERT]


def _headers(role):
    return {"Authorization": f"Bearer {create_access_token(role.lower(), role)}"}


GUEST, INVESTIGATOR, SUPERVISOR = _headers("GUEST"), _headers("INVESTIGATOR"), _headers("SUPERVISOR")
NEW_COMPLAINT = {
    "customer_name": "R. Iyer", "customer_type": "INDIVIDUAL", "account": "XXXX4821", "channel": "UPI",
    "amount": 42000, "occurred_at": "2027-02-14T21:10:00+05:30", "reported_at": "2027-02-15T08:30:00+05:30",
    "cross_border": False, "beneficiary_account": "AC_MULE_1", "beneficiary_bank": "SBI",
    "description": "Caller posing as KYC officer; UPI collect request approved.",
}


@pytest.fixture
def service():
    svc = ComplaintService(repo=ComplaintRepository(), alert_repo=FakeAlerts(), audit=get_audit_service(),
                           provider=None, now_fn=lambda: NOW)
    svc.seed_demo()
    return svc


@pytest_asyncio.fixture
async def client(monkeypatch, service):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET", "test_secret_key_for_testing_only_32chars")
    get_settings.cache_clear()
    from api.app import app

    app.dependency_overrides[get_complaint_service] = lambda: service
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_complaint_service, None)
    get_settings.cache_clear()


async def _create(client):
    response = await client.post("/api/v1/complaints", json=NEW_COMPLAINT, headers=INVESTIGATOR)
    assert response.status_code == 200, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_list_shows_seeded_cases_with_deadline_counts(client):
    response = await client.get("/api/v1/complaints", headers=GUEST)

    data = response.json()["data"]
    assert response.status_code == 200
    assert len(data["cases"]) >= 6
    assert data["as_of"].startswith("2027-03-01")
    assert {"open", "due_soon", "overdue", "shadow_credits_pending", "compensation_due", "mule_linked"} <= set(data["summary"])
    assert data["summary"]["overdue"] >= 1


@pytest.mark.asyncio
async def test_new_complaint_starts_the_clock_and_checks_the_beneficiary_against_mule_alerts(client):
    case = await _create(client)

    assert case["complaint_id"].startswith("FC-2027-")
    assert case["deadlines"]["resolve_by"].startswith("2027-04-01")
    assert [e["kind"] for e in case["evidence"]] == ["complaint", "mule_match"]
    assert case["evidence"][1]["data"]["alert_id"] == "ALT_MULE1"
    assert "MULE_BENEFICIARY" in case["finding"]["flags"]


@pytest.mark.asyncio
async def test_evidence_arrives_extends_the_chain_and_moves_the_finding(client):
    case = await _create(client)
    url = f"/api/v1/complaints/{case['complaint_id']}/evidence"
    for item in (
        {"source": "SMS_GATEWAY", "kind": "sms_alert", "at": "2027-02-14T21:10:30+05:30",
         "summary": "Debit alert delivered to the registered mobile", "data": {"delivered": True}},
        {"source": "AUTH_LOG", "kind": "login", "at": "2027-02-14T21:09:00+05:30",
         "summary": "Collect request approved with UPI PIN on the customer's phone", "data": {"new_device": False, "otp_verified": True}},
        {"source": "CUSTOMER", "kind": "credential_disclosed", "at": "2027-02-14T21:05:00+05:30",
         "summary": "Customer approved the request while on a call with the fraudster", "data": {}},
    ):
        response = await client.post(url, json=item, headers=INVESTIGATOR)
        assert response.status_code == 200, response.text

    updated = response.json()["data"]
    assert updated["finding"]["category"] == "CUSTOMER_NEGLIGENCE"
    assert updated["finding"]["proof_complete"] is True
    assert updated["chain"] == {"intact": True, "broken_at": None}
    assert len(updated["replay"]) == len(updated["evidence"]) == 5
    assert [s["category"] for s in updated["replay"][:2]] == ["UNDETERMINED", "THIRD_PARTY_BREACH"]


@pytest.mark.asyncio
async def test_unknown_evidence_kind_is_rejected(client):
    case = await _create(client)
    bad = {"source": "MERCHANT", "kind": "vibes", "at": "2027-02-14T21:10:30+05:30", "summary": "x", "data": {}}

    response = await client.post(f"/api/v1/complaints/{case['complaint_id']}/evidence", json=bad, headers=INVESTIGATOR)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_report_before_the_fraud_is_rejected(client):
    bad = {**NEW_COMPLAINT, "reported_at": "2027-02-14T20:00:00+05:30"}

    response = await client.post("/api/v1/complaints", json=bad, headers=INVESTIGATOR)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_only_supervisors_record_decisions_and_only_once(client):
    case = await _create(client)
    url = f"/api/v1/complaints/{case['complaint_id']}/decision"
    decision = {"outcome": "ZERO_LIABILITY", "customer_liability": 0, "notes": "Money landed in a known mule account."}

    assert (await client.post(url, json=decision, headers=INVESTIGATOR)).status_code == 403
    first = await client.post(url, json=decision, headers=SUPERVISOR)
    again = await client.post(url, json=decision, headers=SUPERVISOR)

    assert first.status_code == 200
    assert first.json()["data"]["status"] == "RESOLVED"
    assert first.json()["data"]["decision"]["decided_by"] == "supervisor"
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_liability_above_the_amount_is_rejected(client):
    case = await _create(client)
    decision = {"outcome": "CUSTOMER_LIABLE", "customer_liability": 999999, "notes": "x"}

    response = await client.post(f"/api/v1/complaints/{case['complaint_id']}/decision", json=decision, headers=SUPERVISOR)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_narrative_cites_evidence(client):
    case = await _create(client)

    response = await client.get(f"/api/v1/complaints/{case['complaint_id']}/narrative", headers=GUEST)

    sentences = response.json()["data"]["sentences"]
    assert response.status_code == 200
    assert sentences and all(s["evidence"] for s in sentences)


@pytest.mark.asyncio
async def test_evidence_pack_as_json_and_pdf_for_staff_only(client):
    case = await _create(client)
    base = f"/api/v1/complaints/{case['complaint_id']}"

    pack = await client.get(f"{base}/pack", headers=INVESTIGATOR)
    pdf = await client.get(f"{base}/pack.pdf", headers=INVESTIGATOR)

    assert pack.status_code == 200
    assert pack.json()["data"]["chain"]["intact"] is True
    assert pack.json()["data"]["narrative"]["sentences"]
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    for path in ("/pack", "/pack.pdf"):
        assert (await client.get(f"{base}{path}", headers=GUEST)).status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path"), [("POST", ""), ("POST", "/FC-2027-000101/evidence"), ("POST", "/FC-2027-000101/decision")])
async def test_guest_cannot_change_complaints(client, method, path):
    response = await client.request(method, f"/api/v1/complaints{path}", json={}, headers=GUEST)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unknown_case_is_404(client):
    response = await client.get("/api/v1/complaints/FC-2027-999999", headers=GUEST)

    assert response.status_code == 404
