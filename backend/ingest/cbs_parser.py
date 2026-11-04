"""
CBS Log Parser
Reads structured bank logs and normalises to MuleCatch transaction format.
Supports JSON and CSV formats from IOB Core Banking System.
"""

import csv
import json
from datetime import datetime, timezone
from typing import Dict, List


def parse_cbs_log_line(line: str) -> Dict:
    """Parse a single CBS log JSON entry"""
    try:
        raw = json.loads(line)
        return {
            "txn_id": raw.get("txn_ref") or raw.get("txn_id", ""),
            "from_account": raw.get("dr_account") or raw.get("from_account", ""),
            "to_account": raw.get("cr_account") or raw.get("to_account", ""),
            "amount": float(raw.get("amount", 0)),
            "timestamp": raw.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "device_id": raw.get("device_id", "UNKNOWN"),
            "ip_address": raw.get("ip_address", "0.0.0.0"),
            "upi_id": raw.get("upi_id", ""),
            "txn_type": raw.get("txn_type", "UPI_PUSH"),
            "pattern": "NORMAL",
            "is_suspicious": False,
        }
    except (json.JSONDecodeError, ValueError):
        return {}


def parse_cbs_file(filepath: str) -> List[Dict]:
    """Parse a CBS log file (one JSON object per line)"""
    transactions = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line:
                t = parse_cbs_log_line(line)
                if t.get("txn_id"):
                    transactions.append(t)
    return transactions


def parse_upi_csv(filepath: str) -> List[Dict]:
    """Parse UPI transaction export CSV"""
    transactions = []
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                transactions.append(
                    {
                        "txn_id": row.get("Transaction ID", ""),
                        "from_account": row.get("Debit Account", ""),
                        "to_account": row.get("Credit Account", ""),
                        "amount": float(row.get("Amount", 0)),
                        "timestamp": row.get("Timestamp", ""),
                        "device_id": row.get("Device ID", "UNKNOWN"),
                        "ip_address": row.get("IP Address", "0.0.0.0"),
                        "upi_id": row.get("UPI ID", ""),
                        "txn_type": "UPI_PUSH",
                        "pattern": "NORMAL",
                        "is_suspicious": False,
                    }
                )
            except (ValueError, KeyError):
                continue
    return transactions
