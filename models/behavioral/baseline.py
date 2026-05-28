"""
Account Behavioral Baseline Comparison
=======================================
Compares each account's current-window activity against its historical
baseline (avg_monthly_txn, account_age, typical amounts) to produce a
deviation score.  High deviation = the account is doing something it
has never done before, a strong mule indicator.

Eight signals:
  1. Volume deviation   – current txn count vs historical average
  2. Amount deviation   – current avg amount vs historical norm
  3. Recipient burst    – unique recipients vs expected diversity
  4. Balance retention  – mules don't retain funds (low retention = high risk)
  5. Beneficiary entropy – Shannon entropy of recipient distribution
  6. Temporal regularity – bot-like timing detection (low CoV = suspicious)
  7. Inbound/outbound asymmetry – mules receive far more than they spend
  8. Dormancy burst     – dormant account suddenly activates
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
    balance_retention: float = 0.0     # 0-1, low retention = mule-like
    beneficiary_entropy: float = 0.0   # 0-1, high entropy = distributing widely
    temporal_regularity: float = 0.0   # 0-1, bot-like regular timing
    inbound_outbound_asymmetry: float = 0.0  # 0-1, mules receive >> spend
    dormancy_burst: float = 0.0        # 0-1, dormant then sudden activity
    composite_score: float = 0.0       # weighted blend of above
    reason_codes: List[str] = field(default_factory=list)


WEIGHTS = {
    "volume":    0.25,
    "amount":    0.15,
    "recipient": 0.12,
    "retention": 0.12,
    "entropy":   0.10,
    "temporal":  0.08,
    "asymmetry": 0.10,
    "dormancy":  0.08,
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
    incoming: Dict[str, List[Dict]] = {}
    for t in transactions:
        outgoing.setdefault(t["from_account"], []).append(t)
        incoming.setdefault(t["to_account"], []).append(t)

    acc_map = {a["account_id"]: a for a in accounts}
    results: Dict[str, BaselineDeviation] = {}

    for acc_id, acc in acc_map.items():
        out_txns = outgoing.get(acc_id, [])
        in_txns = incoming.get(acc_id, [])
        dev = _score_account(acc_id, acc, out_txns, in_txns)
        results[acc_id] = dev

    return results


def _score_account(
    acc_id: str,
    acc: Dict,
    txns: List[Dict],
    in_txns: List[Dict] = None,
) -> BaselineDeviation:
    in_txns = in_txns or []
    dev = BaselineDeviation(account_id=acc_id)
    if not txns and not in_txns:
        return dev

    # Historical baseline from account metadata
    avg_monthly = acc.get("avg_monthly_txn", DEFAULT_AVG_MONTHLY_TXN) or DEFAULT_AVG_MONTHLY_TXN
    account_age = acc.get("account_age_days", 30)

    # ── 1. Volume deviation ──────────────────────────────────────────────
    current_count = len(txns)
    expected = max(avg_monthly, 1)
    ratio = current_count / expected
    dev.volume_deviation = min(1.0, max(0, 1 - 1 / (ratio + 0.01)))

    if account_age < 7 and current_count > 3:
        dev.volume_deviation = min(1.0, dev.volume_deviation + 0.2)

    # ── 2. Amount deviation ──────────────────────────────────────────────
    amounts = [float(t["amount"]) for t in txns]
    avg_amount = sum(amounts) / len(amounts) if amounts else 0
    expected_avg = DEFAULT_AVG_AMOUNT
    if avg_amount > expected_avg * 2:
        dev.amount_deviation = min(1.0, (avg_amount - expected_avg) / (expected_avg * 3))
    elif avg_amount < expected_avg * 0.2 and current_count > 10:
        dev.amount_deviation = min(1.0, 0.5 + (10 - avg_amount / 1000) * 0.05)

    # ── 3. Recipient burst ───────────────────────────────────────────────
    unique_recipients = len(set(t["to_account"] for t in txns)) if txns else 0
    expected_recipients = min(DEFAULT_UNIQUE_RECIPIENTS, avg_monthly)
    if unique_recipients > expected_recipients:
        dev.recipient_burst = min(
            1.0, (unique_recipients - expected_recipients) / max(expected_recipients, 1)
        )

    # ── 4. Balance retention (BL04) ──────────────────────────────────────
    total_in = sum(float(t["amount"]) for t in in_txns)
    total_out = sum(float(t["amount"]) for t in txns)
    if total_in > 0:
        retention = max(0.0, 1.0 - (total_out / total_in))
        # Low retention = mule-like (funds pass through)
        dev.balance_retention = min(1.0, max(0.0, 1.0 - retention))
    elif total_out > 0:
        dev.balance_retention = 0.8  # spending without receiving is unusual

    # ── 5. Beneficiary entropy (BL05) ────────────────────────────────────
    if txns:
        recipient_counts: Dict[str, int] = {}
        for t in txns:
            recipient_counts[t["to_account"]] = recipient_counts.get(t["to_account"], 0) + 1
        total = sum(recipient_counts.values())
        if total > 0 and len(recipient_counts) > 1:
            entropy = -sum(
                (c / total) * math.log2(c / total)
                for c in recipient_counts.values()
                if c > 0
            )
            max_entropy = math.log2(len(recipient_counts))
            normalized = entropy / max_entropy if max_entropy > 0 else 0
            # High entropy = distributing evenly to many recipients = suspicious
            dev.beneficiary_entropy = min(1.0, normalized)

    # ── 6. Temporal regularity (BL06) ────────────────────────────────────
    if len(txns) >= 3:
        timestamps = []
        for t in txns:
            ts = t.get("timestamp", "")
            if isinstance(ts, str) and len(ts) >= 19:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    timestamps.append(dt.timestamp())
                except (ValueError, TypeError):
                    pass
        if len(timestamps) >= 3:
            timestamps.sort()
            intervals = [
                timestamps[i + 1] - timestamps[i]
                for i in range(len(timestamps) - 1)
            ]
            mean_interval = sum(intervals) / len(intervals)
            if mean_interval > 0:
                std_interval = (
                    sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
                ) ** 0.5
                cov = std_interval / mean_interval
                # Low CoV = very regular timing = bot-like
                if cov < 0.15:
                    dev.temporal_regularity = 0.9
                elif cov < 0.3:
                    dev.temporal_regularity = 0.6
                elif cov < 0.5:
                    dev.temporal_regularity = 0.3

    # ── 7. Inbound/outbound asymmetry (BL07) ────────────────────────────
    if total_in > 0 or total_out > 0:
        total_flow = total_in + total_out
        if total_flow > 0:
            asymmetry = abs(total_in - total_out) / total_flow
            # Mules typically receive much more than they send out personally
            if total_in > total_out * 3:
                dev.inbound_outbound_asymmetry = min(1.0, asymmetry)
            elif total_out > total_in * 3:
                dev.inbound_outbound_asymmetry = min(1.0, asymmetry * 0.5)

    # ── 8. Dormancy burst (BL08) ────────────────────────────────────────
    if account_age > 90 and avg_monthly < 3 and current_count > 8:
        dev.dormancy_burst = min(1.0, current_count / 15.0)
    elif account_age > 180 and avg_monthly < 2 and current_count > 5:
        dev.dormancy_burst = min(1.0, current_count / 10.0)

    # ── Composite ────────────────────────────────────────────────────────
    dev.composite_score = (
        WEIGHTS["volume"]    * dev.volume_deviation +
        WEIGHTS["amount"]    * dev.amount_deviation +
        WEIGHTS["recipient"] * dev.recipient_burst +
        WEIGHTS["retention"] * dev.balance_retention +
        WEIGHTS["entropy"]   * dev.beneficiary_entropy +
        WEIGHTS["temporal"]  * dev.temporal_regularity +
        WEIGHTS["asymmetry"] * dev.inbound_outbound_asymmetry +
        WEIGHTS["dormancy"]  * dev.dormancy_burst
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
    if dev.balance_retention > 0.6:
        dev.reason_codes.append(
            f"BL04: Low balance retention — {dev.balance_retention:.0%} of inbound funds forwarded"
        )
    if dev.beneficiary_entropy > 0.6:
        dev.reason_codes.append(
            f"BL05: High beneficiary entropy ({dev.beneficiary_entropy:.2f}) — "
            f"evenly distributing to {unique_recipients} recipients"
        )
    if dev.temporal_regularity > 0.5:
        dev.reason_codes.append(
            f"BL06: Bot-like temporal regularity (score={dev.temporal_regularity:.2f})"
        )
    if dev.inbound_outbound_asymmetry > 0.5:
        dev.reason_codes.append(
            f"BL07: Inbound/outbound asymmetry — in=₹{total_in:,.0f} vs out=₹{total_out:,.0f}"
        )
    if dev.dormancy_burst > 0.4:
        dev.reason_codes.append(
            f"BL08: Dormant account burst — {current_count} txns after "
            f"{account_age}d with avg {avg_monthly}/month"
        )

    return dev
