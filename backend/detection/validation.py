"""Row-level validation of raw transactions before they reach the detectors.

A bad row is rejected with a reason and the rest of the batch is scored; one
malformed record must not take the whole run down (docs/buildx/05-evaluation.md 7.6).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

REQUIRED_ACCOUNT_FIELDS = ("from_account", "to_account")


@dataclass(frozen=True)
class RowRejection:
    index: int
    txn_id: Optional[str]
    reason: str


def _amount_problem(row: Dict) -> Optional[str]:
    if "amount" not in row or row["amount"] in (None, ""):
        return "amount missing"
    try:
        amount = float(row["amount"])
    except (TypeError, ValueError):
        return f"amount not numeric: {row['amount']!r}"
    if not math.isfinite(amount) or amount < 0:
        return f"amount must be a non-negative number: {row['amount']!r}"
    return None


def _timestamp_problem(row: Dict) -> Optional[str]:
    ts = row.get("timestamp")
    if ts in (None, ""):
        return "timestamp missing"
    if isinstance(ts, datetime):
        return None
    try:
        datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return f"timestamp not ISO-8601: {ts!r}"
    return None


def _row_problem(row: Dict) -> Optional[str]:
    if not isinstance(row, dict):
        return "row is not a mapping"
    for field in REQUIRED_ACCOUNT_FIELDS:
        if not row.get(field):
            return f"{field} missing"
    return _amount_problem(row) or _timestamp_problem(row)


def validate_transactions(transactions: List[Dict]) -> Tuple[List[Dict], Tuple[RowRejection, ...]]:
    """Split a batch into usable rows and per-row rejections. Inputs are not modified."""
    valid: List[Dict] = []
    rejected: List[RowRejection] = []
    seen_ids = set()
    for index, row in enumerate(transactions):
        txn_id = row.get("txn_id") if isinstance(row, dict) else None
        problem = _row_problem(row)
        if problem is None and txn_id is not None:
            if txn_id in seen_ids:
                problem = f"duplicate txn_id {txn_id}"
            else:
                seen_ids.add(txn_id)
        if problem is None:
            valid.append(row)
        else:
            rejected.append(RowRejection(index=index, txn_id=txn_id, reason=problem))
    return valid, tuple(rejected)
