"""
Jan Dhan Account Risk Detector
================================
Detects suspicious activity on Basic Savings Bank Deposit Accounts (BSBDA)
commonly opened under the Pradhan Mantri Jan Dhan Yojana.

Money mules frequently exploit these low-KYC accounts for layering.

Signals:
  JD01: BSBDA with >10 transactions in 24 hours         (weight 0.30)
  JD02: Dormant >90 days then sudden high activity       (weight 0.30)
  JD03: BSBDA receiving from multiple tier-1 city accts  (weight 0.20)
  JD04: Tier-2/3 city account transacting with urban     (weight 0.20)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class JanDhanRiskResult:
    """Immutable assessment result for a Jan Dhan / BSBDA account."""

    account_id: str
    is_bsbda: bool
    activity_spike_score: float  # 0.0-1.0
    reason_codes: tuple  # tuple of reason-code strings
    composite_score: float  # 0.0-1.0 weighted blend


# Signal weights
_WEIGHTS: Dict[str, float] = {
    "JD01": 0.30,
    "JD02": 0.30,
    "JD03": 0.20,
    "JD04": 0.20,
}

# Tier-1 cities in India (metro / urban hubs)
_TIER1_CITIES = frozenset(
    {
        "mumbai",
        "delhi",
        "bangalore",
        "bengaluru",
        "hyderabad",
        "chennai",
        "kolkata",
        "pune",
        "ahmedabad",
    }
)


def _is_bsbda(account: Dict) -> bool:
    """Check whether the account is a BSBDA / Jan Dhan account."""
    acc_type = (account.get("account_type") or "").upper()
    if acc_type in ("BSBDA", "JAN_DHAN"):
        return True
    return bool(account.get("is_jan_dhan", False))


def _parse_ts(raw: str) -> datetime:
    """Best-effort ISO timestamp parsing."""
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.min


class JanDhanDetector:
    """Assess Jan Dhan / BSBDA accounts for mule-related risk signals."""

    def assess(
        self,
        account: Dict,
        transactions: List[Dict],
    ) -> JanDhanRiskResult:
        """Run all JD signals and return a composite risk result."""
        acc_id = account.get("account_id", "UNKNOWN")
        bsbda = _is_bsbda(account)

        signals: Dict[str, float] = {}
        reasons: List[str] = []

        # ── JD01: High transaction volume in 24h ────────────────────
        jd01, jd01_reason = self._jd01_volume_spike(bsbda, transactions)
        signals["JD01"] = jd01
        if jd01_reason:
            reasons.append(jd01_reason)

        # ── JD02: Dormancy then sudden burst ────────────────────────
        jd02, jd02_reason = self._jd02_dormancy_burst(account, transactions)
        signals["JD02"] = jd02
        if jd02_reason:
            reasons.append(jd02_reason)

        # ── JD03: Inflows from tier-1 cities ────────────────────────
        jd03, jd03_reason = self._jd03_tier1_inflows(bsbda, account, transactions)
        signals["JD03"] = jd03
        if jd03_reason:
            reasons.append(jd03_reason)

        # ── JD04: Tier-2/3 transacting with urban accounts ─────────
        jd04, jd04_reason = self._jd04_urban_mismatch(account, transactions)
        signals["JD04"] = jd04
        if jd04_reason:
            reasons.append(jd04_reason)

        # ── Composite ───────────────────────────────────────────────
        composite = sum(_WEIGHTS[code] * score for code, score in signals.items())
        composite = min(composite, 1.0)

        # Activity spike is max of JD01 and JD02
        activity_spike = max(signals.get("JD01", 0.0), signals.get("JD02", 0.0))

        return JanDhanRiskResult(
            account_id=acc_id,
            is_bsbda=bsbda,
            activity_spike_score=activity_spike,
            reason_codes=tuple(reasons),
            composite_score=round(composite, 4),
        )

    # ── Signal implementations ───────────────────────────────────────

    @staticmethod
    def _jd01_volume_spike(
        is_bsbda: bool,
        transactions: List[Dict],
    ) -> Tuple[float, str]:
        """JD01: BSBDA with >10 transactions in any 24h window."""
        if not is_bsbda or not transactions:
            return 0.0, ""

        timestamps = sorted(_parse_ts(t.get("timestamp", "")) for t in transactions)
        max_in_window = 0

        for i, ts in enumerate(timestamps):
            window_end = ts + timedelta(hours=24)
            count = sum(1 for t in timestamps[i:] if t <= window_end)
            max_in_window = max(max_in_window, count)

        if max_in_window > 10:
            score = min(1.0, max_in_window / 20.0)
            return score, (
                f"JD01: BSBDA account with {max_in_window} transactions "
                f"in 24h window (threshold: 10)"
            )
        return 0.0, ""

    @staticmethod
    def _jd02_dormancy_burst(
        account: Dict,
        transactions: List[Dict],
    ) -> Tuple[float, str]:
        """JD02: Dormant >90 days then sudden activity."""
        dormant_days = account.get("days_since_last_txn", 0)
        if dormant_days < 90 or len(transactions) < 3:
            return 0.0, ""

        score = min(1.0, len(transactions) / 15.0)
        return score, (
            f"JD02: Account dormant {dormant_days} days then "
            f"{len(transactions)} transactions detected"
        )

    @staticmethod
    def _jd03_tier1_inflows(
        is_bsbda: bool,
        account: Dict,
        transactions: List[Dict],
    ) -> Tuple[float, str]:
        """JD03: BSBDA receiving funds from multiple tier-1 city accounts."""
        if not is_bsbda:
            return 0.0, ""

        acc_id = account.get("account_id", "")
        tier1_senders: set = set()

        for txn in transactions:
            if txn.get("to_account") == acc_id or txn.get("direction") == "INBOUND":
                sender_city = (txn.get("sender_city") or "").lower()
                if sender_city in _TIER1_CITIES:
                    tier1_senders.add(txn.get("from_account", ""))

        if len(tier1_senders) >= 3:
            score = min(1.0, len(tier1_senders) / 6.0)
            return score, (
                f"JD03: BSBDA receiving from {len(tier1_senders)} tier-1 city accounts"
            )
        return 0.0, ""

    @staticmethod
    def _jd04_urban_mismatch(
        account: Dict,
        transactions: List[Dict],
    ) -> Tuple[float, str]:
        """JD04: Tier-2/3 city account transacting with high-value urban accounts."""
        acc_city = (account.get("city") or "").lower()
        if acc_city in _TIER1_CITIES or not acc_city:
            return 0.0, ""

        urban_counterparties: set = set()
        for txn in transactions:
            cp_city = (
                txn.get("counterparty_city") or txn.get("sender_city") or ""
            ).lower()
            if cp_city in _TIER1_CITIES:
                cp_id = txn.get("from_account") or txn.get("to_account") or ""
                urban_counterparties.add(cp_id)

        if len(urban_counterparties) >= 2:
            score = min(1.0, len(urban_counterparties) / 5.0)
            return score, (
                f"JD04: Tier-2/3 city ({acc_city}) account transacting with "
                f"{len(urban_counterparties)} urban counterparties"
            )
        return 0.0, ""
