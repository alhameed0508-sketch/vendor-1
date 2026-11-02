"""Complaint desk service: seeded demo desk, mule checks, decisions and evidence after a decision."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from complaints.seed import DEMO_NOW, FALLBACK_BENEFICIARY
from core.exceptions import ConflictError
from repositories.complaint_repository import ComplaintRepository
from services.complaint_service import ComplaintService

MULE = {"alert_id": "ALT_7", "risk_score": 0.91, "nodes": [{"account_id": "AC_M", "role": "MULE", "bank": "SBI"}]}


class Alerts:
    def __init__(self, alerts=None, error=None):
        self._alerts, self._error = alerts or [], error

    def find_all(self, **kwargs):
        if self._error:
            raise self._error
        return self._alerts


class Audit:
    def __init__(self):
        self.actions = []

    def log(self, action, *args, **kwargs):
        self.actions.append(action)


def _service(alerts=None, audit=None):
    svc = ComplaintService(
        repo=ComplaintRepository(),
        alert_repo=alerts or Alerts([MULE]),
        audit=audit or Audit(),
        provider=None,
        now_fn=lambda: DEMO_NOW,
    )
    svc.seed_demo()
    return svc


def test_demo_desk_has_one_case_in_each_state():
    desk = _service().list_cases()
    assert desk["summary"] == {
        "open": 7,
        "due_soon": 1,
        "overdue": 1,
        "shadow_credits_pending": 1,
        "compensation_due": 21_250,
        "mule_linked": 1,
        "amount_disputed": 651_749,
    }
    assert desk["cases"][0]["overdue"] is True  # most urgent first


def test_seeded_mule_case_points_at_a_live_alert():
    case = _service().get_case("FC-2027-000101")
    assert case["beneficiary_account"] == "AC_M"
    assert case["mule_link"]["alert_id"] == "ALT_7"


def test_without_alerts_no_mule_match_is_invented():
    svc = _service(alerts=Alerts(error=ConnectionError("neo4j down")))
    case = svc.get_case("FC-2027-000101")
    assert case["beneficiary_account"] == FALLBACK_BENEFICIARY
    assert case["mule_link"] is None
    assert svc.list_cases()["summary"]["mule_linked"] == 0


def test_decision_records_whether_it_followed_the_recommendation_and_closes_evidence():
    audit = Audit()
    svc = _service(audit=audit)
    decided = svc.decide("FC-2027-000102", "SHARED_LIABILITY", 10_000, "Customer was coached by the caller.", "sup")
    assert decided["decision"]["recommended_customer_liability"] == 28_000
    assert decided["decision"]["followed_recommendation"] is False
    assert decided["decision"]["within_time_limit"] is True
    assert "COMPLAINT_DECIDED" in audit.actions
    with pytest.raises(ConflictError):
        svc.add_evidence(
            "FC-2027-000102",
            {
                "at": "2027-02-27T10:00:00+05:30",
                "source": "CUSTOMER",
                "kind": "ncrp_report",
                "summary": "late",
                "data": {},
            },
            "inv",
        )


def test_bank_policy_case_has_no_number_to_follow():
    decided = _service().decide("FC-2027-000105", "SHARED_LIABILITY", 60_000, "Board policy: 25% after day 5.", "sup")
    assert decided["decision"]["followed_recommendation"] is None
    assert decided["decision"]["within_time_limit"] is False


def test_tampered_evidence_shows_where_the_chain_breaks():
    svc = _service()
    case = svc._repo.find_by_id("FC-2027-000104")
    edited = [*case["evidence"][:2], {**case["evidence"][2], "summary": "edited"}, *case["evidence"][3:]]
    svc._repo.update("FC-2027-000104", evidence=edited)
    assert svc.get_case("FC-2027-000104")["chain"] == {"intact": False, "broken_at": "E3"}
