"""Access policy: a pure decision over role, institution, office scope and assignment."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from access.models import CaseScope, Decision, UserContext
from access.policy import can, can_open

BRANCH_CASE = CaseScope("A", "A-BR1", ("A-BR1", "A-RG1", "A-HO"), assignee="inv1")
UNASSIGNED = CaseScope("A", "A-BR1", ("A-BR1", "A-RG1", "A-HO"), assignee=None)


def _user(role, institution="A", office="A-BR1", user_id="inv1"):
    return UserContext(user_id, role, institution, office)


@pytest.mark.parametrize(
    ("user", "case", "action", "allowed"),
    [
        # investigator: own office, writes only when assigned
        (_user("INVESTIGATOR"), BRANCH_CASE, "read", True),
        (_user("INVESTIGATOR"), BRANCH_CASE, "write", True),
        (_user("INVESTIGATOR"), BRANCH_CASE, "escalate", True),
        (_user("INVESTIGATOR", user_id="inv2"), BRANCH_CASE, "read", True),
        (_user("INVESTIGATOR", user_id="inv2"), BRANCH_CASE, "write", False),
        (_user("INVESTIGATOR", user_id="inv2"), BRANCH_CASE, "escalate", False),
        (_user("INVESTIGATOR"), UNASSIGNED, "write", False),
        (_user("INVESTIGATOR"), BRANCH_CASE, "assign", False),
        (_user("INVESTIGATOR"), BRANCH_CASE, "close", False),
        # investigator in another office of the same bank
        (_user("INVESTIGATOR", office="A-BR2"), BRANCH_CASE, "read", False),
        # investigator in another institution
        (_user("INVESTIGATOR", institution="B", office="B-BR1"), BRANCH_CASE, "read", False),
        # supervisor: whole subtree of their office
        (_user("SUPERVISOR", office="A-HO", user_id="sup"), BRANCH_CASE, "read", True),
        (_user("SUPERVISOR", office="A-HO", user_id="sup"), BRANCH_CASE, "write", True),
        (_user("SUPERVISOR", office="A-HO", user_id="sup"), BRANCH_CASE, "assign", True),
        (_user("SUPERVISOR", office="A-HO", user_id="sup"), BRANCH_CASE, "close", True),
        (_user("SUPERVISOR", office="A-RG1", user_id="sup"), BRANCH_CASE, "close", True),
        (_user("SUPERVISOR", office="A-BR2", user_id="sup"), BRANCH_CASE, "read", False),
        (_user("SUPERVISOR", institution="B", office="B-HO", user_id="sup"), BRANCH_CASE, "read", False),
        # read-only staff
        (_user("READONLY", user_id="ro"), BRANCH_CASE, "read", True),
        (_user("READONLY", user_id="ro"), BRANCH_CASE, "write", False),
        (_user("READONLY", institution="B", office="B-BR1", user_id="ro"), BRANCH_CASE, "read", False),
        # platform administrator
        (UserContext("root", "ADMIN", None, None), BRANCH_CASE, "close", True),
        # guests and unknown roles never pass
        (_user("GUEST", user_id="g"), BRANCH_CASE, "read", False),
        (_user("MYSTERY", user_id="m"), BRANCH_CASE, "read", False),
    ],
)
def test_decision_matrix(user, case, action, allowed):
    decision = can(user, action, case)
    assert isinstance(decision, Decision)
    assert decision.allowed is allowed
    assert decision.reason


def test_unknown_action_is_denied():
    assert can(_user("SUPERVISOR", office="A-HO", user_id="s"), "delete_everything", BRANCH_CASE).allowed is False


def test_a_case_without_an_institution_is_visible_only_to_the_platform_admin():
    orphan = CaseScope(None, None, (), assignee=None)
    assert can(_user("SUPERVISOR", office="A-HO", user_id="s"), "read", orphan).allowed is False
    assert can(UserContext("root", "ADMIN", None, None), "read", orphan).allowed is True


@pytest.mark.parametrize(
    ("role", "expected"),
    [("INVESTIGATOR", True), ("SUPERVISOR", True), ("ADMIN", True), ("READONLY", False), ("GUEST", False)],
)
def test_who_may_open_a_case(role, expected):
    institution = None if role == "ADMIN" else "A"
    assert can_open(UserContext("u", role, institution, "A-BR1")).allowed is expected
