"""
Account Behavioral Baseline Comparison
=======================================
Compares each account's current-window activity against its historical
baseline (avg_monthly_txn, account_age, typical amounts) to produce a
deviation score.  High deviation = the account is doing something it
has never done before, a strong mule indicator.

Three signals:
  1. Volume deviation   – current txn count vs historical average
  2. Amount deviation   – current avg amount vs historical norm
  3. Recipient burst    – unique recipients vs expected diversity
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
import math


@dataclass
class BaselineDeviation:
    account_id: str
    volume_deviation: float = 0.0      # 0-1, how much txn count exceeds baseline
    amount_deviation: float = 0.0      # 0-1, how much avg amount deviates
    recipient_burst: float = 0.0       # 0-1, unusual recipient diversity
    composite_score: float = 0.0       # weighted blend of above
    reason_codes: List[str] = field(default_factory=list)


WEIGHTS = {
    "volume":    0.45,
    "amount":    0.30,
    "recipient": 0.25,
}

# Default baseline assumptions when historical data is sparse
DEFAULT_AVG_MONTHLY_TXN = 8
DEFAULT_AVG_AMOUNT = 15_000.0
DEFAULT_UNIQUE_RECIPIENTS = 4


def compute_baselines(
    accounts: List[Dict],
    transactions: List[Dict],
) -> Dict[str, BaselineDeviation]:
    """Score every account's current-window deviation from its baseline."""
    # Group transactions by sender
    outgoing: Dict[str, List[Dict]] = {}
    for t in transactions:
        outgoing.setdefault(t["from_account"], []).append(t)

    acc_map = {a["account_id"]: a for a in accounts}
    results: Dict[str, BaselineDeviation] = {}

    for acc_id, acc in acc_map.items():
        txns = outgoing.get(acc_id, [])
        dev = _score_account(acc_id, acc, txns)
        results[acc_id] = dev

    return results


def _score_account(
    acc_id: str,
    acc: Dict,
    txns: List[Dict],
) -> BaselineDeviation:
    dev = BaselineDeviation(account_id=acc_id)
    if not txns:
        return dev

    # Historical baseline from account metadata
    avg_monthly = acc.get("avg_monthly_txn", DEFAULT_AVG_MONTHLY_TXN) or DEFAULT_AVG_MONTHLY_TXN
    account_age = acc.get("account_age_days", 30)

    # ── 1. Volume deviation ──────────────────────────────────────────────
    current_count = len(txns)
    # Scale expected count: if avg_monthly is 8, expect ~8 txns per 30-day window
    expected = max(avg_monthly, 1)
    ratio = current_count / expected
    # Sigmoid-like: ratio of 1 → 0, ratio of 3+ → ~1.0
    dev.volume_deviation = min(1.0, max(0, 1 - 1 / (ratio + 0.01)))

    # Very young accounts get an automatic boost
    if account_age < 7 and current_count > 3:
        dev.volume_deviation = min(1.0, dev.volume_deviation + 0.2)

    # ── 2. Amount deviation ──────────────────────────────────────────────
    amounts = [float(t["amount"]) for t in txns]
    avg_amount = sum(amounts) / len(amounts) if amounts else 0
    # Compare against historical norm (or default)
    expected_avg = DEFAULT_AVG_AMOUNT
    if avg_amount > expected_avg * 2:
        dev.amount_deviation = min(1.0, (avg_amount - expected_avg) / (expected_avg * 3))
    elif avg_amount < expected_avg * 0.2 and current_count > 10:
        # Many tiny transactions — smurfing signature
        dev.amount_deviation = min(1.0, 0.5 + (10 - avg_amount / 1000) * 0.05)

    # ── 3. Recipient burst ───────────────────────────────────────────────
    unique_recipients = len(set(t["to_account"] for t in txns))
    expected_recipients = min(DEFAULT_UNIQUE_RECIPIENTS, avg_monthly)
    if unique_recipients > expected_recipients:
        dev.recipient_burst = min(
            1.0, (unique_recipients - expected_recipients) / max(expected_recipients, 1)
        )

    # ── Composite ────────────────────────────────────────────────────────
    dev.composite_score = (
        WEIGHTS["volume"]    * dev.volume_deviation +
        WEIGHTS["amount"]    * dev.amount_deviation +
        WEIGHTS["recipient"] * dev.recipient_burst
    )
    dev.composite_score = min(dev.composite_score, 1.0)

    # ── Reason codes ─────────────────────────────────────────────────────
    if dev.volume_deviation > 0.5:
        dev.reason_codes.append(
            f"BL01: Transaction volume {current_count}x exceeds baseline "
            f"(avg {avg_monthly}/month)"
        )
    if dev.amount_deviation > 0.4:
        dev.reason_codes.append(
            f"BL02: Average amount ₹{avg_amount:,.0f} deviates from norm"
        )
    if dev.recipient_burst > 0.4:
        dev.reason_codes.append(
            f"BL03: {unique_recipients} unique recipients vs expected "
            f"{int(expected_recipients)}"
        )

    return dev
