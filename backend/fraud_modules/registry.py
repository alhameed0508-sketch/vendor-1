"""Fraud module registry.

One place states what each detection module can really do. A module's status is derived from
its capabilities, so the UI, the API and the docs can never claim more than the capabilities
list admits. Adding a module means adding one entry here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple


class Status(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"  # code exists, is reachable and tested
    PARTIAL = "PARTIAL"  # some of it exists, or it needs data this repo does not have
    PLANNED = "PLANNED"  # design target only


@dataclass(frozen=True)
class Capability:
    name: str
    status: Status
    note: str = ""  # required whenever status is not IMPLEMENTED: what is missing


@dataclass(frozen=True)
class ModuleSpec:
    module_id: str
    name: str
    purpose: str
    capabilities: Tuple[Capability, ...]
    data_requirements: Tuple[str, ...]
    workspace_path: Optional[str] = None  # None until the module has its own page

    @property
    def status(self) -> Status:
        states = {c.status for c in self.capabilities}
        if not states or states == {Status.PLANNED}:
            return Status.PLANNED
        if states == {Status.IMPLEMENTED}:
            return Status.IMPLEMENTED
        return Status.PARTIAL


def _cap(name: str, status: Status, note: str = "") -> Capability:
    return Capability(name, status, note)


DONE, PART, PLAN = Status.IMPLEMENTED, Status.PARTIAL, Status.PLANNED

MODULES: Tuple[ModuleSpec, ...] = (
    ModuleSpec(
        "mule",
        "Mule account detection",
        "Find mule accounts and the networks that move stolen money through them.",
        (
            _cap("Account link analysis", DONE),
            _cap("Pass-through detection", DONE),
            _cap("Suspicious network communities", DONE),
            _cap("Temporal lifecycle scoring", DONE),
            _cap("Risk scoring with explanations", DONE),
        ),
        ("transactions: from_account, to_account, amount, timestamp",),
        workspace_path="/",
    ),
    ModuleSpec(
        "upi",
        "UPI and digital payments",
        "Spot suspicious UPI and digital payments as they happen.",
        (
            _cap("Velocity and split-payment rules", DONE),
            _cap("High-risk UPI handle pattern", PART, "Needs a upi_id on each account; the AMLworld sample has none."),
            _cap(
                "Shared device across accounts",
                PART,
                "Needs a device_id on each transaction; the AMLworld sample has none.",
            ),
            _cap(
                "New-beneficiary checks",
                PART,
                "A scam-victim detector exists in models/scam but is not on the detection path.",
            ),
            _cap("Session and IP anomalies", PLAN, "No session or IP fields in any data source."),
        ),
        ("transactions with channel = UPI", "upi_id per account", "device_id per transaction"),
    ),
    ModuleSpec(
        "transaction_aml",
        "Transaction and AML intelligence",
        "Spot structuring, layering and other laundering patterns across channels.",
        (
            _cap("Structuring and split payments", DONE),
            _cap("Same-day pass-through layering", DONE),
            _cap("Identical-amount fan-out", DONE),
            _cap("Circular fund flow", PLAN, "The pipeline has no cycle detection on payments."),
            _cap("STR filing", PART, "The workflow and PDF are real; submission to the regulator is simulated."),
        ),
        ("transactions: from_account, to_account, amount, timestamp",),
    ),
    ModuleSpec(
        "identity",
        "Identity and account opening",
        "Find duplicate or synthetic identities and unusual account openings.",
        (
            _cap("Duplicate identity matching", DONE),
            _cap("Early-life account anomaly", DONE),
            _cap("Synthetic identity indicators", PART, "Matching only; no KYC attributes to test consistency."),
            _cap("KYC consistency checks", PLAN, "No KYC records source."),
            _cap("Document verification results", PLAN, "No document-verification feed."),
        ),
        ("applications: name, phone, email, address, government id hash", "KYC records"),
    ),
    ModuleSpec(
        "loan",
        "Loan and lending fraud",
        "Detect fraudulent loan applications and misuse of disbursed funds.",
        (
            _cap(
                "Borrower sanction screening",
                PLAN,
                "A screening service exists but nothing sends loan applications to it.",
            ),
            _cap("Duplicate applicant detection", PLAN, "Needs loan application records."),
            _cap("Beneficiary verification", PLAN, "Needs disbursement and payee records."),
            _cap("Disbursement monitoring", PLAN, "Needs a loan management system feed."),
            _cap("Fund diversion", PLAN, "Needs disbursement and downstream payment data."),
        ),
        ("loan applications", "disbursement events", "repayment history"),
    ),
)

_BY_ID: Dict[str, ModuleSpec] = {m.module_id: m for m in MODULES}


def get_module(module_id: str) -> ModuleSpec:
    return _BY_ID[module_id]


def module_dict(spec: ModuleSpec) -> Dict:
    return {
        "module_id": spec.module_id,
        "name": spec.name,
        "purpose": spec.purpose,
        "status": spec.status.value,
        "workspace_path": spec.workspace_path,
        "data_requirements": list(spec.data_requirements),
        "capabilities": [{"name": c.name, "status": c.status.value, "note": c.note} for c in spec.capabilities],
    }
