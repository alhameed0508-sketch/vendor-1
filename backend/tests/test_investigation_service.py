"""One investigation workflow over alert cases and complaint cases: legal transitions only, every move audited."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.exceptions import ConflictError, NotFoundError, ValidationError
from fraud_modules.intervention import SIMULATED_LABEL, request_intervention
from repositories.audit_repository import AuditRepository
from repositories.investigation_repository import InvestigationRepository
from services.audit_service import AuditService
from services.investigation.investigation_service import InvestigationService


@pytest.fixture
def audit():
    return AuditService(AuditRepository())


@pytest.fixture
def svc(audit):
    resolvers = {"alert": lambda i: i.startswith("AL"), "complaint": lambda i: i.startswith("CMP")}
    return InvestigationService(InvestigationRepository(), audit, resolvers)


def _open(svc, source="alert", source_id="AL1"):
    return svc.open(source, source_id, user="inv1")


def test_a_new_investigation_starts_as_new_and_is_audited(svc, audit):
    inv = _open(svc)
    assert inv["status"] == "NEW"
    assert inv["source"] == "alert" and inv["source_id"] == "AL1"
    assert inv["outcome"] is None and inv["assignee"] is None
    assert [e["action"] for e in audit.get_log(alert_id="AL1")] == ["INVESTIGATION_OPENED"]


def test_alert_and_complaint_cases_share_one_workflow(svc):
    assert _open(svc, "complaint", "CMP-101")["status"] == "NEW"


def test_unknown_source_or_missing_case_is_rejected(svc):
    with pytest.raises(ValidationError):
        svc.open("loan", "X1", user="u")
    with pytest.raises(NotFoundError):
        svc.open("alert", "ZZ9", user="u")


def test_opening_the_same_case_twice_returns_a_conflict(svc):
    _open(svc)
    with pytest.raises(ConflictError):
        _open(svc)


def test_walks_the_full_path_to_closed(svc):
    inv = _open(svc)
    for step in ("UNDER_REVIEW", "INVESTIGATING", "ESCALATED", "INVESTIGATING"):
        inv = svc.transition(inv["investigation_id"], step, user="inv1")
        assert inv["status"] == step
    inv = svc.transition(inv["investigation_id"], "RESOLVED", user="sup1", outcome="CONFIRMED")
    inv = svc.transition(inv["investigation_id"], "CLOSED", user="sup1")
    assert inv["status"] == "CLOSED" and inv["outcome"] == "CONFIRMED"


@pytest.mark.parametrize(
    ("path", "bad"),
    [
        ((), "INVESTIGATING"),
        ((), "RESOLVED"),
        (("UNDER_REVIEW",), "ESCALATED"),
        (("UNDER_REVIEW", "INVESTIGATING"), "CLOSED"),
    ],
)
def test_invalid_transitions_are_rejected_and_do_not_change_status(svc, path, bad):
    inv = _open(svc)
    for step in path:
        inv = svc.transition(inv["investigation_id"], step, user="u")
    with pytest.raises(ConflictError):
        svc.transition(inv["investigation_id"], bad, user="u", outcome="CONFIRMED")
    assert svc.get(inv["investigation_id"])["status"] == (path[-1] if path else "NEW")


def test_resolving_needs_an_outcome_from_the_allowed_set(svc):
    inv = _open(svc)
    for step in ("UNDER_REVIEW", "INVESTIGATING"):
        inv = svc.transition(inv["investigation_id"], step, user="u")
    for bad in (None, "FRAUD", "confirmed"):
        with pytest.raises(ValidationError):
            svc.transition(inv["investigation_id"], "RESOLVED", user="u", outcome=bad)
    for outcome in ("CONFIRMED", "FALSE_POSITIVE", "UNRESOLVED"):
        fresh = _open(svc, source_id=f"AL-{outcome}")
        for step in ("UNDER_REVIEW", "INVESTIGATING"):
            fresh = svc.transition(fresh["investigation_id"], step, user="u")
        assert svc.transition(fresh["investigation_id"], "RESOLVED", user="u", outcome=outcome)["outcome"] == outcome


def test_closed_is_final(svc):
    inv = _open(svc)
    for step in ("UNDER_REVIEW", "INVESTIGATING"):
        inv = svc.transition(inv["investigation_id"], step, user="u")
    svc.transition(inv["investigation_id"], "RESOLVED", user="u", outcome="UNRESOLVED")
    svc.transition(inv["investigation_id"], "CLOSED", user="u")
    with pytest.raises(ConflictError):
        svc.transition(inv["investigation_id"], "INVESTIGATING", user="u")


def test_every_transition_and_assignment_is_in_the_audit_chain_and_the_chain_verifies(svc, audit):
    inv = _open(svc)
    svc.assign(inv["investigation_id"], "analyst7", user="sup1")
    svc.transition(inv["investigation_id"], "UNDER_REVIEW", user="analyst7", note="picked up")
    actions = [e["action"] for e in reversed(audit.get_log(alert_id="AL1"))]
    assert actions == ["INVESTIGATION_OPENED", "INVESTIGATION_ASSIGNED", "INVESTIGATION_UNDER_REVIEW"]
    assert svc.get(inv["investigation_id"])["assignee"] == "analyst7"
    assert audit.verify_integrity()["valid"] is True


def test_history_lists_each_move_with_who_and_when(svc):
    inv = _open(svc)
    inv = svc.transition(inv["investigation_id"], "UNDER_REVIEW", user="analyst7", note="picked up")
    assert [(h["to"], h["by"], h["note"]) for h in inv["history"]] == [
        ("NEW", "inv1", ""),
        ("UNDER_REVIEW", "analyst7", "picked up"),
    ]


def test_get_and_list(svc):
    inv = _open(svc)
    assert svc.get(inv["investigation_id"])["source_id"] == "AL1"
    assert [i["investigation_id"] for i in svc.list_all()] == [inv["investigation_id"]]
    with pytest.raises(NotFoundError):
        svc.get("INV_NOPE")


def test_intervention_is_simulated_labelled_and_audited(svc, audit):
    inv = _open(svc)
    result = request_intervention(audit, kind="HOLD", account_id="ACC-7", investigation=inv, user="sup1")
    assert result["simulated"] is True
    assert result["label"] == SIMULATED_LABEL == "SIMULATED: no bank system connected"
    assert result["status"] == "RECORDED_ONLY"
    entry = audit.get_log(action="INTERVENTION_REQUESTED")[0]
    assert "SIMULATED" in entry["details"] and "ACC-7" in entry["details"]
    assert audit.verify_integrity()["valid"] is True


def test_unknown_intervention_kind_is_rejected(audit):
    with pytest.raises(ValidationError):
        request_intervention(audit, kind="FREEZE_ALL", account_id="A", investigation={"source_id": "AL1"}, user="u")


def test_each_investigation_lists_the_statuses_it_can_move_to(svc):
    inv = _open(svc)
    assert inv["allowed_next"] == ["UNDER_REVIEW"]
    inv = svc.transition(inv["investigation_id"], "UNDER_REVIEW", user="u")
    assert inv["allowed_next"] == ["INVESTIGATING"]
    assert svc.get(inv["investigation_id"])["allowed_next"] == ["INVESTIGATING"]
    assert svc.list_all()[0]["allowed_next"] == ["INVESTIGATING"]
