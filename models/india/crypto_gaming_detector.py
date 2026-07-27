"""
Crypto-Hawala & Gaming Platform Laundering Detector
=====================================================
Detects crypto exchange interactions, hawala-digital hybrid patterns,
and gaming-platform fund laundering commonly seen in Indian mule
networks.

Signals:
  CH01: Funds flowing to known crypto exchange merchants    (weight 0.25)
  CH02: P2P crypto conversion amount patterns               (weight 0.20)
  CH03: Gaming platform merchant codes                      (weight 0.20)
  CH04: Hawala-digital hybrid (cash -> UPI fan-out)         (weight 0.20)
  CH05: Circular gaming wallet flow                         (weight 0.15)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Set, Tuple


@dataclass(frozen=True)
class CryptoHawalaResult:
    """Immutable assessment result for crypto/hawala/gaming signals."""

    account_id: str
    crypto_score: float  # 0.0-1.0
    gaming_score: float  # 0.0-1.0
    hawala_score: float  # 0.0-1.0
    composite_score: float  # 0.0-1.0
    reason_codes: tuple  # tuple of reason-code strings
    flagged_merchants: tuple  # tuple of matched merchant identifiers


# Signal weights
_WEIGHTS: Dict[str, float] = {
    "CH01": 0.25,
    "CH02": 0.20,
    "CH03": 0.20,
    "CH04": 0.20,
    "CH05": 0.15,
}


class CryptoGamingDetector:
    """Detect crypto, gaming, and hawala laundering patterns."""

    # Known crypto exchange merchant IDs / UPI handles
    CRYPTO_MERCHANTS: FrozenSet[str] = frozenset(
        {
            "wazirx",
            "coindcx",
            "mudrex",
            "coinswitch",
            "zebpay",
            "buyucoin",
        }
    )

    # Known gaming / betting merchant IDs
    GAMING_MERCHANTS: FrozenSet[str] = frozenset(
        {
            "dream11",
            "mpl",
            "winzo",
            "parimatch",
            "mahadev",
            "1xbet",
            "betway",
        }
    )

    # P2P crypto conversion amounts (INR equivalents of common USDT values)
    _P2P_AMOUNTS: tuple = (
        8_300,  # ~$100 USDT
        16_600,  # ~$200 USDT
        41_500,  # ~$500 USDT
        83_000,  # ~$1000 USDT
    )

    _P2P_TOLERANCE: float = 0.05  # 5% tolerance for amount matching

    def assess(
        self,
        account: Dict,
        transactions: List[Dict],
    ) -> CryptoHawalaResult:
        """Run all CH signals and return a composite result."""
        acc_id = account.get("account_id", "UNKNOWN")

        signals: Dict[str, float] = {}
        reasons: List[str] = []
        all_flagged: Set[str] = set()

        # ── CH01: Crypto exchange merchants ─────────────────────────
        ch01, ch01_reason, flagged = self._ch01_crypto_merchants(transactions)
        signals["CH01"] = ch01
        all_flagged.update(flagged)
        if ch01_reason:
            reasons.append(ch01_reason)

        # ── CH02: P2P crypto conversion patterns ────────────────────
        ch02, ch02_reason = self._ch02_p2p_patterns(transactions)
        signals["CH02"] = ch02
        if ch02_reason:
            reasons.append(ch02_reason)

        # ── CH03: Gaming platform merchants ─────────────────────────
        ch03, ch03_reason, flagged_g = self._ch03_gaming_merchants(transactions)
        signals["CH03"] = ch03
        all_flagged.update(flagged_g)
        if ch03_reason:
            reasons.append(ch03_reason)

        # ── CH04: Hawala-digital hybrid ─────────────────────────────
        ch04, ch04_reason = self._ch04_hawala_hybrid(transactions)
        signals["CH04"] = ch04
        if ch04_reason:
            reasons.append(ch04_reason)

        # ── CH05: Circular gaming wallet flow ───────────────────────
        ch05, ch05_reason = self._ch05_circular_gaming(transactions)
        signals["CH05"] = ch05
        if ch05_reason:
            reasons.append(ch05_reason)

        # ── Composite ───────────────────────────────────────────────
        composite = sum(_WEIGHTS[code] * score for code, score in signals.items())
        composite = min(composite, 1.0)

        crypto_score = max(signals.get("CH01", 0.0), signals.get("CH02", 0.0))
        gaming_score = max(signals.get("CH03", 0.0), signals.get("CH05", 0.0))
        hawala_score = signals.get("CH04", 0.0)

        return CryptoHawalaResult(
            account_id=acc_id,
            crypto_score=round(crypto_score, 4),
            gaming_score=round(gaming_score, 4),
            hawala_score=round(hawala_score, 4),
            composite_score=round(composite, 4),
            reason_codes=tuple(reasons),
            flagged_merchants=tuple(sorted(all_flagged)),
        )

    # ── Signal implementations ───────────────────────────────────────

    def _ch01_crypto_merchants(
        self,
        transactions: List[Dict],
    ) -> Tuple[float, str, Set[str]]:
        """CH01: Funds flowing to known crypto exchange merchant IDs."""
        flagged: Set[str] = set()
        for txn in transactions:
            merchant = (txn.get("merchant_id") or "").lower()
            upi = (txn.get("upi_handle") or "").lower()
            for identifier in (merchant, upi):
                for crypto in self.CRYPTO_MERCHANTS:
                    if crypto in identifier:
                        flagged.add(crypto)

        if not flagged:
            return 0.0, "", set()

        score = min(1.0, len(flagged) / 3.0)
        return (
            score,
            (f"CH01: Funds flowing to crypto exchanges — {', '.join(sorted(flagged))}"),
            flagged,
        )

    def _ch02_p2p_patterns(
        self,
        transactions: List[Dict],
    ) -> Tuple[float, str]:
        """CH02: P2P crypto conversion amount patterns."""
        matching_count = 0
        for txn in transactions:
            amount = float(txn.get("amount", 0))
            for target in self._P2P_AMOUNTS:
                lower = target * (1 - self._P2P_TOLERANCE)
                upper = target * (1 + self._P2P_TOLERANCE)
                if lower <= amount <= upper:
                    matching_count += 1
                    break

        if matching_count < 2:
            return 0.0, ""

        score = min(1.0, matching_count / 5.0)
        return score, (
            f"CH02: {matching_count} transactions match P2P crypto "
            f"conversion amounts (e.g., multiples of Rs 8,300 / Rs 41,500)"
        )

    def _ch03_gaming_merchants(
        self,
        transactions: List[Dict],
    ) -> Tuple[float, str, Set[str]]:
        """CH03: Gaming platform merchant codes detected."""
        flagged: Set[str] = set()
        for txn in transactions:
            merchant = (txn.get("merchant_id") or "").lower()
            upi = (txn.get("upi_handle") or "").lower()
            for identifier in (merchant, upi):
                for gaming in self.GAMING_MERCHANTS:
                    if gaming in identifier:
                        flagged.add(gaming)

        if not flagged:
            return 0.0, "", set()

        score = min(1.0, len(flagged) / 3.0)
        return (
            score,
            (
                f"CH03: Gaming platform transactions detected — "
                f"{', '.join(sorted(flagged))}"
            ),
            flagged,
        )

    @staticmethod
    def _ch04_hawala_hybrid(
        transactions: List[Dict],
    ) -> Tuple[float, str]:
        """CH04: Cash deposits followed by immediate UPI fan-out."""
        cash_deposits = [
            t
            for t in transactions
            if (t.get("channel") or "").upper() in ("CASH", "CDM", "BRANCH_DEPOSIT")
        ]
        upi_transfers = [
            t
            for t in transactions
            if (t.get("channel") or "").upper() == "UPI"
            and (t.get("direction") or "").upper() in ("OUTBOUND", "DEBIT", "")
        ]

        if not cash_deposits or len(upi_transfers) < 3:
            return 0.0, ""

        unique_upi_recipients = {
            t.get("to_account") or t.get("beneficiary") or "" for t in upi_transfers
        }
        unique_upi_recipients.discard("")

        if len(unique_upi_recipients) < 3:
            return 0.0, ""

        total_cash = sum(float(t.get("amount", 0)) for t in cash_deposits)
        total_upi_out = sum(float(t.get("amount", 0)) for t in upi_transfers)

        # Cash in and UPI out should be roughly balanced for hawala
        if total_cash > 0 and total_upi_out > 0:
            ratio = min(total_cash, total_upi_out) / max(total_cash, total_upi_out)
            if ratio > 0.5:
                score = min(1.0, len(unique_upi_recipients) / 5.0)
                return score, (
                    f"CH04: Hawala-digital hybrid — Rs {total_cash:,.0f} cash "
                    f"deposits then UPI transfers to "
                    f"{len(unique_upi_recipients)} accounts"
                )

        return 0.0, ""

    @staticmethod
    def _ch05_circular_gaming(
        transactions: List[Dict],
    ) -> Tuple[float, str]:
        """CH05: Circular flow through gaming wallets.

        Pattern: deposit to gaming wallet, minimal play, withdrawal
        to a different account.
        """
        gaming_deposits = []
        gaming_withdrawals = []

        for txn in transactions:
            category = (txn.get("category") or "").lower()
            merchant = (txn.get("merchant_id") or "").lower()
            direction = (txn.get("direction") or "").upper()

            is_gaming_related = "gaming" in category or "gaming" in merchant
            if is_gaming_related:
                if direction in ("OUTBOUND", "DEBIT"):
                    gaming_deposits.append(txn)
                elif direction in ("INBOUND", "CREDIT"):
                    gaming_withdrawals.append(txn)

        if not gaming_deposits or not gaming_withdrawals:
            return 0.0, ""

        total_deposit = sum(float(t.get("amount", 0)) for t in gaming_deposits)
        total_withdraw = sum(float(t.get("amount", 0)) for t in gaming_withdrawals)

        if total_deposit == 0:
            return 0.0, ""

        # Minimal play means withdrawal is close to deposit amount
        recovery_ratio = total_withdraw / total_deposit
        if recovery_ratio > 0.80:
            score = min(1.0, recovery_ratio)
            return score, (
                f"CH05: Circular gaming flow — Rs {total_deposit:,.0f} "
                f"deposited, Rs {total_withdraw:,.0f} withdrawn "
                f"({recovery_ratio:.0%} recovery, minimal play)"
            )

        return 0.0, ""
