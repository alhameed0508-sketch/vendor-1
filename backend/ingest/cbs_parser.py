"""
CBS Log Parser
Reads structured bank logs and normalises to MuleCatch transaction format.
Supports JSON and CSV formats from IOB Core Banking System.
"""

import json
from datetime import datetime, timezone
from typing import Dict


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
