"""Module registry: a module's status is derived from its capabilities, so a claim cannot drift from the facts."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fraud_modules.registry import (
    MODULES,
    Capability,
    ModuleSpec,
    Status,
    get_module,
)


def _spec(*statuses):
    caps = tuple(Capability(f"c{i}", s) for i, s in enumerate(statuses))
    return ModuleSpec("x", "X", "purpose", capabilities=caps, data_requirements=())


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ((Status.IMPLEMENTED, Status.IMPLEMENTED), Status.IMPLEMENTED),
        ((Status.PLANNED, Status.PLANNED), Status.PLANNED),
        ((Status.IMPLEMENTED, Status.PLANNED), Status.PARTIAL),
        ((Status.PARTIAL,), Status.PARTIAL),
        ((), Status.PLANNED),
    ],
)
def test_status_is_derived_from_capabilities(statuses, expected):
    assert _spec(*statuses).status is expected


def test_registry_has_the_core_modules_with_unique_ids():
    ids = [m.module_id for m in MODULES]
    assert ids == ["mule", "upi", "transaction_aml", "identity", "loan"]
    assert len(set(ids)) == len(ids)


def test_every_module_with_a_findings_source_has_a_workspace_and_loan_does_not():
    for module_id in ("mule", "upi", "transaction_aml", "identity"):
        assert get_module(module_id).workspace_path == f"/modules/{module_id}"
    assert get_module("loan").workspace_path is None


def test_loan_module_is_a_planned_shell():
    loan = get_module("loan")
    assert loan.status is Status.PLANNED
    planned = {c.name for c in loan.capabilities if c.status is Status.PLANNED}
    assert {"Disbursement monitoring", "Fund diversion", "Beneficiary verification"} <= planned


def test_every_non_implemented_capability_says_what_is_missing():
    for module in MODULES:
        for cap in module.capabilities:
            if cap.status is not Status.IMPLEMENTED:
                assert cap.note, f"{module.module_id}/{cap.name} needs a note"


def test_unknown_module_raises_key_error():
    with pytest.raises(KeyError):
        get_module("nope")


def test_specs_are_immutable():
    with pytest.raises(AttributeError):
        MODULES[0].name = "changed"
