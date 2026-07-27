"""
Tests for PaySim adapter — schema mapping, fraud label extraction.
"""

import sys
import os
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from data.adapters.paysim_adapter import PaySimAdapter


@pytest.fixture
def paysim_csv(tmp_path):
    """Create a small mock PaySim CSV file."""
    csv_path = tmp_path / "paysim_test.csv"
    rows = [
        {
            "step": "1",
            "type": "TRANSFER",
            "amount": "45000.00",
            "nameOrig": "C1000001",
            "oldbalanceOrg": "100000",
            "newbalanceOrig": "55000",
            "nameDest": "C2000001",
            "oldbalanceDest": "0",
            "newbalanceDest": "45000",
            "isFraud": "1",
            "isFlaggedFraud": "0",
        },
        {
            "step": "1",
            "type": "TRANSFER",
            "amount": "42000.00",
            "nameOrig": "C1000001",
            "oldbalanceOrg": "55000",
            "newbalanceOrig": "13000",
            "nameDest": "C2000002",
            "oldbalanceDest": "0",
            "newbalanceDest": "42000",
            "isFraud": "1",
            "isFlaggedFraud": "0",
        },
        {
            "step": "2",
            "type": "PAYMENT",
            "amount": "5000.00",
            "nameOrig": "C3000001",
            "oldbalanceOrg": "50000",
            "newbalanceOrig": "45000",
            "nameDest": "M4000001",
            "oldbalanceDest": "10000",
            "newbalanceDest": "15000",
            "isFraud": "0",
            "isFlaggedFraud": "0",
        },
        {
            "step": "3",
            "type": "CASH_OUT",
            "amount": "80000.00",
            "nameOrig": "C5000001",
            "oldbalanceOrg": "100000",
            "newbalanceOrig": "20000",
            "nameDest": "C6000001",
            "oldbalanceDest": "0",
            "newbalanceDest": "80000",
            "isFraud": "0",
            "isFlaggedFraud": "0",
        },
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return str(csv_path)


class TestPaySimAdapter:
    def test_load_returns_transactions_and_accounts(self, paysim_csv):
        adapter = PaySimAdapter()
        transactions, accounts = adapter.load(paysim_csv)
        assert len(transactions) == 4
        assert len(accounts) > 0

    def test_transaction_schema(self, paysim_csv):
        adapter = PaySimAdapter()
        transactions, _ = adapter.load(paysim_csv)

        required_fields = {
            "txn_id",
            "from_account",
            "to_account",
            "amount",
            "timestamp",
            "is_suspicious",
            "pattern",
        }
        for txn in transactions:
            for field in required_fields:
                assert field in txn, f"Missing field: {field}"

    def test_fraud_labels_extracted(self, paysim_csv):
        adapter = PaySimAdapter()
        transactions, accounts = adapter.load(paysim_csv)

        # First two transactions are fraud
        fraud_txns = [t for t in transactions if t["is_suspicious"]]
        assert len(fraud_txns) == 2

        # Fraud source accounts should be marked
        fraud_accounts = [a for a in accounts if a.get("is_fraud")]
        assert len(fraud_accounts) > 0

    def test_account_roles_derived(self, paysim_csv):
        adapter = PaySimAdapter()
        _, accounts = adapter.load(paysim_csv)

        roles = {a["role"] for a in accounts}
        assert "SOURCE" in roles or "MULE" in roles
        assert "LEGIT" in roles

    def test_amounts_preserved(self, paysim_csv):
        adapter = PaySimAdapter()
        transactions, _ = adapter.load(paysim_csv)
        amounts = [t["amount"] for t in transactions]
        assert 45000.0 in amounts
        assert 42000.0 in amounts

    def test_max_rows_limit(self, paysim_csv):
        adapter = PaySimAdapter()
        transactions, _ = adapter.load(paysim_csv, max_rows=2)
        assert len(transactions) == 2

    def test_txn_type_mapping(self, paysim_csv):
        adapter = PaySimAdapter()
        transactions, _ = adapter.load(paysim_csv)
        types = {t["txn_type"] for t in transactions}
        # TRANSFER -> NEFT, PAYMENT -> UPI_PUSH, CASH_OUT -> CASH_WITHDRAWAL
        assert "NEFT" in types
        assert "UPI_PUSH" in types
        assert "CASH_WITHDRAWAL" in types

    def test_account_attributes(self, paysim_csv):
        adapter = PaySimAdapter()
        _, accounts = adapter.load(paysim_csv)

        required_attrs = {
            "account_id",
            "role",
            "bank",
            "city",
            "account_age_days",
            "kyc_status",
        }
        for acc in accounts:
            for attr in required_attrs:
                assert attr in acc, f"Missing attribute: {attr}"
            assert acc["bank"] in [
                "IOB",
                "SBI",
                "HDFC",
                "ICICI",
                "PNB",
                "BOB",
                "UNION",
                "CANARA",
            ]

    def test_deterministic_output(self, paysim_csv):
        """Same input should produce same output (deterministic hashing)."""
        adapter = PaySimAdapter()
        txns1, accs1 = adapter.load(paysim_csv)
        txns2, accs2 = adapter.load(paysim_csv)

        assert len(txns1) == len(txns2)
        for t1, t2 in zip(txns1, txns2):
            assert t1["txn_id"] == t2["txn_id"]
            assert t1["amount"] == t2["amount"]
