"""
UPI Regulatory Compliance Monitor
===================================
Monitors UPI transaction patterns for compliance with RBI regulations:
  - Annual UPI credit ceiling (proposed Rs 25 lakh)
  - Cooling period for large / new-beneficiary transfers
  - Collect-request abuse detection

Signals:
  UC01: Annual UPI credit approaching Rs 25 lakh ceiling  (weight 0.25)
  UC02: Transactions >Rs 10,000 — cooling period flag      (weight 0.20)
  UC03: New beneficiary + large transfer in cooling window  (weight 0.25)
  UC04: Multiple UPI collect requests from same handle      (weight 0.15)
  UC05: Post-Oct-2025 P2P collect pattern migration         (weight 0.15)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class UPIComplianceResult:
    """Immutable result of a UPI compliance assessment."""
    account_id: str
    annual_upi_credit: float
    limit_proximity_pct: float     # How close to Rs 25 lakh ceiling (0-100)
    cooling_period_applicable: bool
    flags: tuple                    # tuple of flag strings
    composite_score: float          # 0.0-1.0


# Signal weights
_WEIGHTS: Dict[str, float] = {
    "UC01": 0.25,
    "UC02": 0.20,
    "UC03": 0.25,
    "UC04": 0.15,
    "UC05": 0.15,
}


def _parse_ts(raw) -> datetime:
    """Best-effort ISO timestamp parsing."""
    if isinstance(raw, datetime):
        return raw
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.min


class UPIComplianceMonitor:
    """Monitor UPI transactions for regulatory compliance signals."""

    ANNUAL_UPI_LIMIT: float = 2_500_000.0   # Rs 25 lakh (proposed RBI rule)
    COOLING_THRESHOLD: float = 10_000.0      # Rs 10,000 cooling period threshold
    COOLING_PERIOD_HOURS: int = 4            # 4-hour cooling period window

    def assess(
        self,
        account: Dict,
        transactions: List[Dict],
    ) -> UPIComplianceResult:
        """Run all UC signals and return a composite compliance result."""
        acc_id = account.get("account_id", "UNKNOWN")

        upi_txns = [
            t for t in transactions
            if (t.get("channel") or "").upper() == "UPI"
        ]

        signals: Dict[str, float] = {}
        flags: List[str] = []

        # ── UC01: Annual UPI credit approaching ceiling ─────────────
        uc01, uc01_flag, annual_credit = self._uc01_annual_ceiling(upi_txns)
        signals["UC01"] = uc01
        if uc01_flag:
            flags.append(uc01_flag)

        # ── UC02: Large transactions needing cooling period ─────────
        uc02, uc02_flag = self._uc02_cooling_flag(upi_txns)
        signals["UC02"] = uc02
        if uc02_flag:
            flags.append(uc02_flag)

        # ── UC03: New beneficiary + large transfer ──────────────────
        uc03, uc03_flag = self._uc03_new_beneficiary_large(account, upi_txns)
        signals["UC03"] = uc03
        if uc03_flag:
            flags.append(uc03_flag)

        # ── UC04: Multiple collect requests from same handle ────────
        uc04, uc04_flag = self._uc04_collect_abuse(upi_txns)
        signals["UC04"] = uc04
        if uc04_flag:
            flags.append(uc04_flag)

        # ── UC05: P2P collect pattern migration ─────────────────────
        uc05, uc05_flag = self._uc05_p2p_collect_migration(upi_txns)
        signals["UC05"] = uc05
        if uc05_flag:
            flags.append(uc05_flag)

        # ── Composite ───────────────────────────────────────────────
        composite = sum(
            _WEIGHTS[code] * score for code, score in signals.items()
        )
        composite = min(composite, 1.0)

        proximity_pct = (annual_credit / self.ANNUAL_UPI_LIMIT) * 100.0
        proximity_pct = min(proximity_pct, 100.0)

        cooling_applicable = signals.get("UC02", 0.0) > 0 or signals.get("UC03", 0.0) > 0

        return UPIComplianceResult(
            account_id=acc_id,
            annual_upi_credit=round(annual_credit, 2),
            limit_proximity_pct=round(proximity_pct, 2),
            cooling_period_applicable=cooling_applicable,
            flags=tuple(flags),
            composite_score=round(composite, 4),
        )

    def should_delay_payment(
        self,
        transaction: Dict,
        account: Dict,
        recent_transactions: List[Dict],
    ) -> Tuple[bool, str]:
        """Determine whether a payment should be delayed for cooling period.

        Returns (should_delay, reason_string).
        """
        amount = float(transaction.get("amount", 0))
        channel = (transaction.get("channel") or "").upper()

        if channel != "UPI":
            return False, ""

        # Rule 1: Amount exceeds cooling threshold
        if amount >= self.COOLING_THRESHOLD:
            beneficiary = transaction.get("to_account") or transaction.get("beneficiary") or ""
            known = account.get("known_beneficiaries") or []
            is_new = beneficiary not in known

            if is_new and beneficiary:
                return True, (
                    f"New beneficiary '{beneficiary}' with amount "
                    f"Rs {amount:,.0f} exceeds cooling threshold "
                    f"Rs {self.COOLING_THRESHOLD:,.0f}"
                )

        # Rule 2: Rapid successive large payments
        recent_upi = [
            t for t in recent_transactions
            if (t.get("channel") or "").upper() == "UPI"
            and float(t.get("amount", 0)) >= self.COOLING_THRESHOLD
        ]
        if len(recent_upi) >= 3:
            return True, (
                f"{len(recent_upi)} large UPI payments (>=Rs {self.COOLING_THRESHOLD:,.0f}) "
                f"in recent window — cooling period recommended"
            )

        return False, ""

    # ── Signal implementations ───────────────────────────────────────

    def _uc01_annual_ceiling(
        self,
        upi_txns: List[Dict],
    ) -> Tuple[float, str, float]:
        """UC01: Annual UPI credit approaching Rs 25 lakh ceiling."""
        annual_credit = sum(
            float(t.get("amount", 0))
            for t in upi_txns
            if (t.get("direction") or "").upper() in ("INBOUND", "CREDIT")
        )

        if annual_credit < self.ANNUAL_UPI_LIMIT * 0.7:
            return 0.0, "", annual_credit

        proximity = annual_credit / self.ANNUAL_UPI_LIMIT
        score = min(1.0, (proximity - 0.7) / 0.3)  # Scale 0.7-1.0 -> 0-1
        return score, (
            f"UC01: Annual UPI credit Rs {annual_credit:,.0f} is "
            f"{proximity:.0%} of Rs {self.ANNUAL_UPI_LIMIT:,.0f} ceiling"
        ), annual_credit

    def _uc02_cooling_flag(
        self,
        upi_txns: List[Dict],
    ) -> Tuple[float, str]:
        """UC02: Transactions > Rs 10,000 flagged for cooling period."""
        large_txns = [
            t for t in upi_txns
            if float(t.get("amount", 0)) >= self.COOLING_THRESHOLD
        ]

        if not large_txns:
            return 0.0, ""

        score = min(1.0, len(large_txns) / 5.0)
        total = sum(float(t.get("amount", 0)) for t in large_txns)
        return score, (
            f"UC02: {len(large_txns)} transactions exceed Rs "
            f"{self.COOLING_THRESHOLD:,.0f} (total Rs {total:,.0f})"
        )

    @staticmethod
    def _uc03_new_beneficiary_large(
        account: Dict,
        upi_txns: List[Dict],
    ) -> Tuple[float, str]:
        """UC03: New beneficiary + large transfer within cooling window."""
        known = set(account.get("known_beneficiaries") or [])
        new_large: List[Dict] = []

        for txn in upi_txns:
            beneficiary = txn.get("to_account") or txn.get("beneficiary") or ""
            amount = float(txn.get("amount", 0))
            if beneficiary and beneficiary not in known and amount >= 10_000:
                new_large.append(txn)

        if not new_large:
            return 0.0, ""

        score = min(1.0, len(new_large) / 3.0)
        total = sum(float(t.get("amount", 0)) for t in new_large)
        return score, (
            f"UC03: {len(new_large)} large transfers to new beneficiaries "
            f"(total Rs {total:,.0f}) within cooling window"
        )

    @staticmethod
    def _uc04_collect_abuse(
        upi_txns: List[Dict],
    ) -> Tuple[float, str]:
        """UC04: Multiple UPI collect requests from same handle."""
        collect_txns = [
            t for t in upi_txns
            if (t.get("upi_type") or "").upper() == "COLLECT"
        ]
        if not collect_txns:
            return 0.0, ""

        handle_counts: Dict[str, int] = {}
        for txn in collect_txns:
            handle = (txn.get("upi_handle") or txn.get("from_upi") or "").lower()
            if handle:
                handle_counts[handle] = handle_counts.get(handle, 0) + 1

        if not handle_counts:
            return 0.0, ""

        max_handle = max(handle_counts, key=handle_counts.get)  # type: ignore[arg-type]
        max_count = handle_counts[max_handle]

        if max_count < 3:
            return 0.0, ""

        score = min(1.0, max_count / 8.0)
        return score, (
            f"UC04: {max_count} collect requests from handle "
            f"'{max_handle}'"
        )

    @staticmethod
    def _uc05_p2p_collect_migration(
        upi_txns: List[Dict],
    ) -> Tuple[float, str]:
        """UC05: Post-Oct-2025 P2P collect pattern — migration indicator.

        Detects accounts that suddenly shifted from PAY to COLLECT mode
        after regulatory changes, suggesting the account is being used
        to pull funds from victims.
        """
        collect_count = 0
        pay_count = 0
        for txn in upi_txns:
            upi_type = (txn.get("upi_type") or "").upper()
            if upi_type == "COLLECT":
                collect_count += 1
            elif upi_type == "PAY":
                pay_count += 1

        total = collect_count + pay_count
        if total < 5 or collect_count < 3:
            return 0.0, ""

        collect_ratio = collect_count / total
        if collect_ratio > 0.6:
            score = min(1.0, collect_ratio)
            return score, (
                f"UC05: {collect_ratio:.0%} of UPI transactions are "
                f"COLLECT-initiated ({collect_count}/{total}) — "
                f"potential mule pull pattern"
            )

        return 0.0, ""
