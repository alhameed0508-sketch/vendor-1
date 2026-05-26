"""
PaySim dataset adapter — maps PaySim CSV to MuleCatch format.

PaySim schema:
  step, type, amount, nameOrig, oldbalanceOrg, newbalanceOrig,
  nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud

MuleCatch format:
  Transactions: txn_id, from_account, to_account, amount, timestamp, is_suspicious, ...
  Accounts: account_id, role, bank, city, account_age_days, kyc_status, ...
"""

from __future__ import annotations

import csv
import hashlib
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

BANKS = ["IOB", "SBI", "HDFC", "ICICI", "PNB", "BOB", "UNION", "CANARA"]
CITIES = ["Chennai", "Mumbai", "Delhi", "Kolkata", "Hyderabad", "Pune", "Bengaluru"]


class PaySimAdapter:
    """Maps PaySim CSV data to MuleCatch transaction/account format."""

    def load(
        self, csv_path: str, max_rows: int = 50000
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Load PaySim CSV and return (transactions, accounts).

        Args:
            csv_path: Path to PaySim CSV file
            max_rows: Maximum rows to load (0 = unlimited)

        Returns:
            Tuple of (transactions_list, accounts_list)
        """
        raw_rows = self._read_csv(csv_path, max_rows)
        transactions = self._map_transactions(raw_rows)
        accounts = self._derive_accounts(raw_rows, transactions)
        logger.info(
            "PaySim loaded: %d transactions, %d accounts",
            len(transactions), len(accounts),
        )
        return transactions, accounts

    @staticmethod
    def _read_csv(csv_path: str, max_rows: int) -> List[Dict]:
        """Read CSV rows into list of dicts."""
        rows = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if max_rows and i >= max_rows:
                    break
                rows.append(row)
        return rows

    def _map_transactions(self, rows: List[Dict]) -> List[Dict]:
        """Map PaySim rows to MuleCatch transaction format."""
        base_time = datetime.now() - timedelta(days=7)
        transactions = []

        for row in rows:
            step = int(row.get("step", 0))
            txn_type = row.get("type", "TRANSFER")
            amount = float(row.get("amount", 0))
            name_orig = row.get("nameOrig", "")
            name_dest = row.get("nameDest", "")
            is_fraud = int(row.get("isFraud", 0)) == 1

            # Derive timestamp from step (each step = 1 hour in PaySim)
            timestamp = (base_time + timedelta(hours=step)).isoformat()

            # Generate deterministic txn_id from row data
            txn_hash = hashlib.md5(
                f"{name_orig}{name_dest}{amount}{step}".encode()
            ).hexdigest()[:12]

            transactions.append({
                "txn_id": f"PS_{txn_hash.upper()}",
                "from_account": name_orig,
                "to_account": name_dest,
                "amount": round(amount, 2),
                "timestamp": timestamp,
                "txn_type": self._map_txn_type(txn_type),
                "is_suspicious": is_fraud,
                "pattern": "FRAUD" if is_fraud else "NORMAL",
                "device_id": "",
                "ip_address": "",
                "upi_id": "",
            })

        return transactions

    def _derive_accounts(
        self, rows: List[Dict], transactions: List[Dict]
    ) -> List[Dict]:
        """Derive account objects from transaction data."""
        # Collect unique accounts and their fraud status
        account_info: Dict[str, Dict] = {}

        for row in rows:
            is_fraud = int(row.get("isFraud", 0)) == 1
            orig = row.get("nameOrig", "")
            dest = row.get("nameDest", "")

            if orig and orig not in account_info:
                account_info[orig] = {
                    "is_fraud_source": False,
                    "txn_count": 0,
                    "total_amount": 0.0,
                }
            if dest and dest not in account_info:
                account_info[dest] = {
                    "is_fraud_source": False,
                    "txn_count": 0,
                    "total_amount": 0.0,
                }

            if orig:
                account_info[orig]["txn_count"] += 1
                account_info[orig]["total_amount"] += float(row.get("amount", 0))
                if is_fraud:
                    account_info[orig]["is_fraud_source"] = True

        accounts = []
        rng = random.Random(42)  # Deterministic

        for acc_id, info in account_info.items():
            is_fraud = info["is_fraud_source"]
            # Assign role based on fraud status
            if is_fraud:
                role = "SOURCE" if info["txn_count"] > 3 else "MULE"
            else:
                role = "LEGIT"

            # Derive realistic account attributes
            acc_hash = int(hashlib.md5(acc_id.encode()).hexdigest()[:8], 16)
            bank_idx = acc_hash % len(BANKS)
            city_idx = (acc_hash >> 4) % len(CITIES)

            accounts.append({
                "account_id": acc_id,
                "role": role,
                "is_suspicious": is_fraud,
                "is_fraud": is_fraud,
                "bank": BANKS[bank_idx],
                "city": CITIES[city_idx],
                "account_age_days": rng.randint(1, 365) if not is_fraud else rng.randint(1, 14),
                "kyc_status": "PENDING" if is_fraud and rng.random() > 0.3 else "VERIFIED",
                "upi_id": f"{acc_id[:8].lower()}@upi",
                "avg_monthly_txn": info["txn_count"],
            })

        return accounts

    @staticmethod
    def _map_txn_type(paysim_type: str) -> str:
        """Map PaySim transaction type to MuleCatch type."""
        mapping = {
            "CASH_IN": "CASH_DEPOSIT",
            "CASH_OUT": "CASH_WITHDRAWAL",
            "DEBIT": "UPI_PUSH",
            "PAYMENT": "UPI_PUSH",
            "TRANSFER": "NEFT",
        }
        return mapping.get(paysim_type.upper(), "UPI_PUSH")
