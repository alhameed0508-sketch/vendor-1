"""Directory: seeded demo banks, user-to-context mapping and office paths."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from access.seed import demo_directory


def test_two_synthetic_banks_one_public_one_private():
    d = demo_directory()
    kinds = {i.kind for i in d.institutions}
    assert kinds == {"PUBLIC", "PRIVATE"}
    assert all("Synthetic" in i.name for i in d.institutions)


def test_office_path_runs_from_the_office_up_to_head_office():
    assert demo_directory().office_path("A-BR1") == ("A-BR1", "A-RG1", "A-HO")
    assert demo_directory().office_path("A-HO") == ("A-HO",)
    assert demo_directory().office_path("nowhere") == ()


def test_demo_logins_map_to_employees():
    d = demo_directory()
    inv = d.context_for({"sub": "investigator", "role": "INVESTIGATOR"})
    sup = d.context_for({"sub": "supervisor", "role": "SUPERVISOR"})
    assert (inv.institution_id, inv.office_id) == ("A", "A-BR1")
    assert (sup.institution_id, sup.office_id) == ("A", "A-HO")


def test_admin_has_no_institution_and_unknown_users_have_no_context():
    d = demo_directory()
    admin = d.context_for({"sub": "admin", "role": "ADMIN"})
    assert admin.role == "ADMIN" and admin.institution_id is None
    assert d.context_for({"sub": "stranger", "role": "INVESTIGATOR"}) is None
    assert d.context_for({"sub": "guest", "role": "GUEST"}) is None


def test_the_role_comes_from_the_token_not_the_directory():
    d = demo_directory()
    downgraded = d.context_for({"sub": "supervisor", "role": "READONLY"})
    assert downgraded.role == "READONLY"


def test_scope_for_carries_the_office_path():
    scope = demo_directory().scope_for("A", "A-BR1", "inv1")
    assert scope.office_path == ("A-BR1", "A-RG1", "A-HO") and scope.assignee == "inv1"
