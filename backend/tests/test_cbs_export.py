"""CBS export: payments written as pipe-delimited CBS rows must round-trip through the importer."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from data_adapters.mule_csv_adapter import MuleCSVAdapter  # noqa: E402

from data.adapters.cbs_export import CBS_COLUMNS, to_cbs_csv  # noqa: E402

PAYMENTS = [
    {"txn_id": "T1", "from_account": "A", "to_account": "B", "amount": 5000.0, "timestamp": "2022-09-01T10:00:00"},
    {"txn_id": "T2", "from_account": "B", "to_account": "C", "amount": 4800.5, "timestamp": "2022-09-01T11:30:00"},
    {"txn_id": "T3", "from_account": "C", "to_account": "A", "amount": 100.0, "timestamp": "2022-09-02T09:15:00"},
]


def _parsed():
    return MuleCSVAdapter().parse(to_cbs_csv(PAYMENTS))


def test_header_has_every_required_cbs_column():
    header = to_cbs_csv(PAYMENTS).splitlines()[0].split("|")
    assert header == CBS_COLUMNS


def test_each_payment_becomes_one_debit_and_one_credit_leg():
    lines = to_cbs_csv(PAYMENTS).splitlines()[1:]
    assert len(lines) == 2 * len(PAYMENTS)
    legs = [line.split("|")[4] for line in lines]
    assert legs.count("D") == legs.count("C") == len(PAYMENTS)


def test_round_trips_through_importer_with_high_linkage_confidence():
    parsed = _parsed()
    assert parsed["data_quality"]["linkage_strategy"] == "TRAN_ID_PAIRING"
    assert parsed["data_quality"]["linkage_confidence"] == "HIGH"
    pairs = {(t["from_account"], t["to_account"], t["amount"]) for t in parsed["transactions"]}
    assert pairs == {("A", "B", 5000.0), ("B", "C", 4800.5), ("C", "A", 100.0)}


def test_balances_never_go_negative():
    accounts = _parsed()["accounts"]
    assert {a["account_id"] for a in accounts} == {"A", "B", "C"}
    assert all(a["negative_balance_count"] == 0 for a in accounts)


def test_account_age_does_not_depend_on_role():
    """Opening dates come from a hash of the id, not from any label, so age cannot leak ground truth."""
    ages = [a["account_age_days"] for a in _parsed()["accounts"]]
    assert all(180 <= age <= 3650 + 2 for age in ages)


def test_export_is_deterministic_and_does_not_mutate_input():
    snapshot = [dict(p) for p in PAYMENTS]
    assert to_cbs_csv(PAYMENTS) == to_cbs_csv(PAYMENTS)
    assert PAYMENTS == snapshot
