"""Write payments as pipe-delimited core-banking (CBS) rows for the Data Import page.

Each payment becomes two legs (a debit on the sender, a credit on the receiver) that share a
TRAN_ID, so the importer links them with high confidence. Fields the payments do not carry are
derived from a hash of the account id: the same recipe for every account, so nothing in the file
reveals which accounts are mules.
"""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from io import StringIO
from typing import Dict, Mapping, Sequence

CBS_COLUMNS = [
    "TRAN_DATE",
    "TRAN_ID",
    "TRAN_TYPE",
    "TRAN_SUB_TYPE",
    "PART_TRAN_TYPE",
    "ACID",
    "TRAN_AMT",
    "balance",
    "channel",
    "CIF_ID",
    "ACCT_OPN_DATE",
    "LIEN_AMT",
    "customer_age",
]
CBS_DATE_FORMAT = "%d/%m/%Y %H:%M"
# Channel by amount (rupees): small payments are UPI, large ones move over RTGS.
CHANNEL_CEILINGS = ((100_000, "UPI"), (200_000, "IMPS"), (1_000_000, "NEFT"))
LARGEST_CHANNEL = "RTGS"
MIN_ACCOUNT_AGE_DAYS = 180
ACCOUNT_AGE_SPREAD_DAYS = 3470  # ages land in 180..3,649 days
MIN_CUSTOMER_AGE = 21
CUSTOMER_AGE_SPREAD = 50
OPENING_BALANCE_BUFFER = 1_000.0


def _digest(account_id: str) -> int:
    return int(hashlib.sha256(account_id.encode()).hexdigest()[:12], 16)


def _channel(amount: float) -> str:
    return next((name for ceiling, name in CHANNEL_CEILINGS if amount <= ceiling), LARGEST_CHANNEL)


def _opening_balances(legs: Sequence[tuple]) -> Dict[str, float]:
    """Smallest opening balance (plus a buffer) that keeps every account at or above zero."""
    running: Dict[str, float] = defaultdict(float)
    lowest: Dict[str, float] = defaultdict(float)
    for account, delta in legs:
        running[account] += delta
        lowest[account] = min(lowest[account], running[account])
    return {account: round(-lowest[account] + OPENING_BALANCE_BUFFER, 2) for account in running}


def to_cbs_csv(payments: Sequence[Mapping]) -> str:
    """Render payments (txn_id, from_account, to_account, amount, timestamp) as CBS text."""
    ordered = sorted(payments, key=lambda p: p["timestamp"])
    # Same order the rows are emitted in: debit then credit per payment.
    legs = [
        leg
        for p in ordered
        for leg in ((p["from_account"], -float(p["amount"])), (p["to_account"], float(p["amount"])))
    ]
    balance = _opening_balances(legs)

    first_seen: Dict[str, datetime] = {}
    for p in ordered:
        stamp = datetime.fromisoformat(p["timestamp"])
        first_seen.setdefault(p["from_account"], stamp)
        first_seen.setdefault(p["to_account"], stamp)

    out = StringIO()
    writer = csv.writer(out, delimiter="|", lineterminator="\n")
    writer.writerow(CBS_COLUMNS)
    for p in ordered:
        stamp = datetime.fromisoformat(p["timestamp"])
        amount = round(float(p["amount"]), 2)
        for part, account, delta in (("D", p["from_account"], -amount), ("C", p["to_account"], amount)):
            balance[account] = round(balance[account] + delta, 2)
            seed = _digest(account)
            opened = first_seen[account] - timedelta(days=MIN_ACCOUNT_AGE_DAYS + seed % ACCOUNT_AGE_SPREAD_DAYS)
            writer.writerow(
                [
                    stamp.strftime(CBS_DATE_FORMAT),
                    p["txn_id"],
                    "T",
                    "BI",
                    part,
                    account,
                    f"{amount:.2f}",
                    f"{balance[account]:.2f}",
                    _channel(amount),
                    f"CIF{seed % 10**8:08d}",
                    opened.strftime(CBS_DATE_FORMAT),
                    "0",
                    MIN_CUSTOMER_AGE + (seed >> 8) % CUSTOMER_AGE_SPREAD,
                ]
            )
    return out.getvalue()


def labels_csv(accounts: Sequence[str], is_mule: Mapping[str, bool]) -> str:
    """Ground truth, kept out of the import file: one row per account."""
    out = StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["account_id", "is_mule"])
    for account in sorted(accounts):
        writer.writerow([account, int(bool(is_mule.get(account, False)))])
    return out.getvalue()
