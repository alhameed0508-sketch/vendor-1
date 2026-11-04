"""IBM AMLworld adapter: loading, typology matching and case building on a tiny fixture."""

import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from data.adapters.ibm_aml_adapter import CURRENCY_TO_INR, IbmAml  # noqa: E402

HEADER = "Timestamp,From Bank,Account,To Bank,Account,Amount Received,Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering"
ROWS = [
    # laundering fan-out from 1-A to 2-B, 3-C, 4-D
    "2022/09/01 00:06,1,A,2,B,1000.00,US Dollar,1000.00,US Dollar,ACH,1",
    "2022/09/01 00:30,1,A,3,C,2000.00,Euro,2000.00,Euro,ACH,1",
    "2022/09/01 01:00,1,A,4,D,500.00,Rupee,500.00,Rupee,ACH,1",
    # ordinary traffic
    "2022/09/01 02:00,5,E,6,F,10.00,US Dollar,10.00,US Dollar,Cheque,0",
    "2022/09/01 03:00,6,F,5,E,12.00,US Dollar,12.00,US Dollar,Cheque,0",
    "2022/09/01 04:00,1,A,5,E,7.00,US Dollar,7.00,US Dollar,Cash,0",
    "2022/09/01 05:00,7,G,7,G,9.00,US Dollar,9.00,US Dollar,Reinvestment,0",
    "2022/09/01 06:00,8,H,9,I,3.00,Yen,3.00,Yen,Wire,0",
]
PATTERNS = """BEGIN LAUNDERING ATTEMPT - FAN-OUT:  Max 3-degree Fan-Out
2022/09/01 00:06,1,A,2,B,1000.00,US Dollar,1000.00,US Dollar,ACH,1
2022/09/01 00:30,1,A,3,C,2000.00,Euro,2000.00,Euro,ACH,1
2022/09/01 01:00,1,A,4,D,500.00,Rupee,500.00,Rupee,ACH,1
END LAUNDERING ATTEMPT - FAN-OUT
"""


@pytest.fixture()
def aml(tmp_path):
    trans = tmp_path / "trans.csv"
    trans.write_text("\n".join([HEADER, *ROWS]) + "\n")
    patterns = tmp_path / "patterns.txt"
    patterns.write_text(PATTERNS)
    return IbmAml.load(str(trans), str(patterns))


def test_self_payments_are_dropped(aml):
    assert len(aml.frame) == len(ROWS) - 1
    assert (aml.frame.src != aml.frame.dst).all()


def test_amounts_are_converted_to_rupees(aml):
    row = aml.frame[aml.frame.dst == "2-B"].iloc[0]
    assert row.amount_inr == pytest.approx(1000.0 * CURRENCY_TO_INR["US Dollar"])


def test_unknown_currency_is_rejected(tmp_path):
    bad = tmp_path / "t.csv"
    bad.write_text(HEADER + "\n2022/09/01 00:00,1,A,2,B,1,Zorkmid,1,Zorkmid,ACH,0\n")
    with pytest.raises(ValueError, match="Zorkmid"):
        IbmAml.load(str(bad), None)


def test_attempts_group_laundering_rows_by_typology(aml):
    assert [a.typology for a in aml.attempts] == ["FAN-OUT"]
    assert len(aml.attempts[0].rows) == 3


def test_case_contains_attempt_labels_and_scrubbed_payments(aml):
    accounts, txns, is_mule = aml.build_case(random.Random(1), attempts=1, controls=1, neighbor_cap=10)
    assert {a["account_id"] for a in accounts} >= {"1-A", "2-B", "3-C", "4-D"}
    assert is_mule["1-A"] and is_mule["2-B"] and not is_mule.get("5-E", False)
    assert all(set(t) == {"txn_id", "from_account", "to_account", "amount", "timestamp"} for t in txns)
    assert sum(1 for t in txns if t["from_account"] == "1-A" and t["to_account"] in {"2-B", "3-C", "4-D"}) == 3


def test_case_labels_each_laundering_payment(aml):
    _, txns, _ = aml.build_case(random.Random(1), attempts=1, controls=0, neighbor_cap=10)
    laundering = [t for t in txns if t["txn_id"] in aml.laundering_ids]
    assert len(laundering) == 3
