"""Rule-backed modules: run a subset of the existing rules on the rows a module owns, and say what could not run."""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from detection.pipeline import RuleEngine
from fraud_modules.rule_modules import TRANSACTION_AML, UPI

from data.synthetic.generator import build_adversarial_dataset


def _txn(txn_id, src, dst, channel="UPI", device=""):
    return {
        "txn_id": txn_id,
        "from_account": src,
        "to_account": dst,
        "amount": 10.0,
        "timestamp": "2026-01-01T10:00:00",
        "channel": channel,
        "device_id": device,
    }


ACCOUNTS = [{"account_id": a} for a in ("A", "B", "C")]


def test_engine_can_run_a_subset_of_rules():
    txns = [_txn("1", "A", "C", device="D1"), _txn("2", "B", "C", device="D1")]
    all_hits = RuleEngine().evaluate(ACCOUNTS, txns)
    only_r17 = RuleEngine().evaluate(ACCOUNTS, txns, rule_codes={"R17"})
    assert any(h.startswith("R18") for h in all_hits["A"])
    assert all(h.startswith("R17") for hits in only_r17.values() for h in hits)


def test_upi_module_flags_shared_device_on_upi_rows():
    run = UPI.run(ACCOUNTS, [_txn("1", "A", "C", device="D1"), _txn("2", "B", "C", device="D1")])
    flagged = {(f.account_id, f.rule_code) for f in run.findings}
    assert {("A", "R18"), ("B", "R18")} <= flagged
    assert run.module_id == "upi"


def test_upi_module_ignores_rows_on_other_channels():
    run = UPI.run(ACCOUNTS, [_txn("1", "A", "C", "NEFT", "D1"), _txn("2", "B", "C", "NEFT", "D1")])
    assert run.findings == ()
    assert run.rows_considered == 0


def test_upi_module_reports_signals_it_could_not_run():
    run = UPI.run(ACCOUNTS, [_txn("1", "A", "C"), _txn("2", "B", "C")])
    skipped = {s.rule_code: s.reason for s in run.signals_skipped}
    assert "device_id" in skipped["R18"]
    assert "upi_id" in skipped["R15"]
    assert "R18" not in run.signals_run and "R15" not in run.signals_run
    assert "R17" in run.signals_run


def test_a_signal_runs_once_its_data_is_present():
    accounts = [{"account_id": "A", "upi_id": "9876543210123@x"}, {"account_id": "B"}]
    run = UPI.run(accounts, [_txn("1", "A", "B", device="D1")])
    assert {"R15", "R18"} <= set(run.signals_run)
    assert run.signals_skipped == ()


def test_transaction_aml_matches_the_engine_restricted_to_its_rules():
    random.seed(11)
    ds = build_adversarial_dataset(num_clusters=3, num_legit_accounts=60, num_adversarial=20)
    run = TRANSACTION_AML.run(ds["accounts"], ds["transactions"])
    expected = RuleEngine().evaluate(ds["accounts"], ds["transactions"], rule_codes={"R06", "R12", "R14"})
    rule_findings = [f for f in run.findings if f.rule_code != "CF01"]  # CF01 is the cycle detector, not a rule
    assert {f.account_id for f in rule_findings} == set(expected)
    assert {f.rule_code for f in run.findings} <= {"R06", "R12", "R14", "CF01"}
    assert run.findings, "the adversarial dataset should trip at least one AML rule"


def test_module_run_does_not_mutate_its_input():
    txns = [_txn("1", "A", "C", device="D1")]
    snapshot = [dict(t) for t in txns]
    UPI.run(ACCOUNTS, txns)
    assert txns == snapshot


@pytest.mark.parametrize("module", [UPI, TRANSACTION_AML])
def test_empty_input_gives_an_empty_run(module):
    run = module.run([], [])
    assert run.findings == ()
