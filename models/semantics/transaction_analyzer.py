"""
Transaction Semantics Analyzer
================================
Analyzes transaction metadata for mule indicators:
  TS01: Round-amount structuring (sub-50K clustering)
  TS02: Suspicious UPI handle patterns (numeric-heavy)
  TS03: Narration keyword analysis (loan, commission, crypto, etc.)
  TS04: Crypto/gaming wallet interaction detection

Weighted composite: round_amount 0.30, upi_pattern 0.25,
                    narration 0.25, crypto_gaming 0.20
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────

STRUCTURING_THRESHOLD = 50_000  # INR threshold for CTR reporting
STRUCTURING_BAND = (40_000, 49_999)  # Suspicious range just below threshold
ROUND_AMOUNT_MULTIPLES = (1000, 5000, 10000, 25000)

SUSPICIOUS_NARRATION_KEYWORDS = frozenset({
    "loan", "commission", "crypto", "bitcoin", "usdt", "tether",
    "investment return", "forex", "trading profit", "easy money",
    "part time", "work from home", "telegram", "whatsapp job",
    "safe account", "rbi verification", "tax refund", "insurance claim",
    "lottery", "prize", "gift", "donation", "hawala",
})

CRYPTO_MERCHANT_PATTERNS = frozenset({
    "wazirx", "coindcx", "mudrex", "coinswitch", "zebpay",
    "binance", "kucoin", "bybit",
})

GAMING_MERCHANT_PATTERNS = frozenset({
    "dream11", "mpl", "winzo", "parimatch", "mahadev",
    "betway", "1xbet", "stake",
})

SIGNAL_WEIGHTS = {
    "round_amount": 0.30,
    "upi_pattern": 0.25,
    "narration": 0.25,
    "crypto_gaming": 0.20,
}


@dataclass(frozen=True)
class SemanticsResult:
    account_id: str
    round_amount_score: float
    upi_pattern_score: float
    narration_score: float
    crypto_gaming_score: float
    composite_score: float
    reason_codes: Tuple[str, ...]


class TransactionSemanticsAnalyzer:
    """Analyzes transaction metadata for mule-indicative semantics."""

    def analyze(
        self,
        account_id: str,
        transactions: List[Dict],
    ) -> SemanticsResult:
        """Analyze all outgoing transactions for an account."""
        outgoing = [t for t in transactions if t.get("from_account") == account_id]
        if not outgoing:
            return SemanticsResult(
                account_id=account_id,
                round_amount_score=0.0,
                upi_pattern_score=0.0,
                narration_score=0.0,
                crypto_gaming_score=0.0,
                composite_score=0.0,
                reason_codes=(),
            )

        reason_codes: List[str] = []

        # TS01: Round-amount structuring
        round_score = self._score_round_amounts(outgoing)
        if round_score > 0.3:
            near_threshold = sum(
                1 for t in outgoing
                if STRUCTURING_BAND[0] <= float(t["amount"]) <= STRUCTURING_BAND[1]
            )
            reason_codes.append(
                f"TS01: Round-amount structuring detected "
                f"({near_threshold} txns near ₹50K threshold)"
            )

        # TS02: Suspicious UPI handle patterns
        upi_score = self._score_upi_patterns(outgoing)
        if upi_score > 0.3:
            reason_codes.append(
                "TS02: Suspicious UPI handle patterns (numeric-heavy handles)"
            )

        # TS03: Narration keyword analysis
        narration_score = self._score_narrations(outgoing)
        if narration_score > 0.3:
            reason_codes.append(
                "TS03: Suspicious narration keywords detected"
            )

        # TS04: Crypto/gaming wallet interaction
        crypto_score = self._score_crypto_gaming(outgoing)
        if crypto_score > 0.3:
            reason_codes.append(
                "TS04: Crypto/gaming platform interaction detected"
            )

        composite = (
            SIGNAL_WEIGHTS["round_amount"] * round_score +
            SIGNAL_WEIGHTS["upi_pattern"] * upi_score +
            SIGNAL_WEIGHTS["narration"] * narration_score +
            SIGNAL_WEIGHTS["crypto_gaming"] * crypto_score
        )

        return SemanticsResult(
            account_id=account_id,
            round_amount_score=round(round_score, 4),
            upi_pattern_score=round(upi_score, 4),
            narration_score=round(narration_score, 4),
            crypto_gaming_score=round(crypto_score, 4),
            composite_score=round(min(composite, 1.0), 4),
            reason_codes=tuple(reason_codes),
        )

    def analyze_batch(
        self,
        accounts: List[Dict],
        transactions: List[Dict],
    ) -> Dict[str, SemanticsResult]:
        """Analyze all accounts in a batch."""
        results = {}
        for acc in accounts:
            acc_id = acc["account_id"]
            results[acc_id] = self.analyze(acc_id, transactions)
        return results

    @staticmethod
    def _score_round_amounts(txns: List[Dict]) -> float:
        """Score for round-amount structuring (sub-50K clustering)."""
        if not txns:
            return 0.0

        near_threshold = 0
        round_multiples = 0

        for t in txns:
            amt = float(t["amount"])
            if STRUCTURING_BAND[0] <= amt <= STRUCTURING_BAND[1]:
                near_threshold += 1
            if any(amt > 0 and amt % m == 0 for m in ROUND_AMOUNT_MULTIPLES):
                round_multiples += 1

        total = len(txns)
        near_ratio = near_threshold / total if total > 0 else 0
        round_ratio = round_multiples / total if total > 0 else 0

        # High score if many txns cluster just below threshold
        score = 0.0
        if near_threshold >= 3 and near_ratio > 0.5:
            score = min(1.0, 0.6 + near_ratio * 0.4)
        elif near_threshold >= 2:
            score = min(1.0, 0.3 + near_ratio * 0.3)
        elif round_ratio > 0.8 and total >= 5:
            score = 0.4

        return score

    @staticmethod
    def _score_upi_patterns(txns: List[Dict]) -> float:
        """Score for suspicious UPI handle patterns."""
        suspicious_count = 0
        total_with_upi = 0

        for t in txns:
            upi_handle = t.get("to_upi", "") or t.get("upi_id", "")
            if not upi_handle:
                continue
            total_with_upi += 1

            # Numeric-heavy UPI handles (>60% digits, length >10)
            digit_ratio = sum(1 for c in upi_handle if c.isdigit()) / max(len(upi_handle), 1)
            if digit_ratio > 0.6 and len(upi_handle) > 10:
                suspicious_count += 1

            # Random-looking handles (no recognizable words)
            if re.match(r'^[a-z0-9]{10,}@', upi_handle):
                suspicious_count += 1

        if total_with_upi == 0:
            return 0.0

        ratio = suspicious_count / total_with_upi
        if ratio > 0.7:
            return 0.9
        elif ratio > 0.4:
            return 0.6
        elif ratio > 0.2:
            return 0.3
        return 0.0

    @staticmethod
    def _score_narrations(txns: List[Dict]) -> float:
        """Score for suspicious narration keywords."""
        hit_count = 0
        total_with_narration = 0

        for t in txns:
            narration = (t.get("narration", "") or t.get("remarks", "") or "").lower()
            if not narration:
                continue
            total_with_narration += 1

            for keyword in SUSPICIOUS_NARRATION_KEYWORDS:
                if keyword in narration:
                    hit_count += 1
                    break

        if total_with_narration == 0:
            return 0.0

        ratio = hit_count / total_with_narration
        if ratio > 0.5:
            return 0.9
        elif ratio > 0.3:
            return 0.6
        elif ratio > 0.1:
            return 0.3
        return 0.0

    @staticmethod
    def _score_crypto_gaming(txns: List[Dict]) -> float:
        """Score for crypto/gaming wallet interactions."""
        crypto_hits = 0
        gaming_hits = 0

        for t in txns:
            # Check merchant ID, UPI handle, and narration
            fields_to_check = [
                (t.get("merchant_id", "") or "").lower(),
                (t.get("to_upi", "") or "").lower(),
                (t.get("narration", "") or "").lower(),
                (t.get("to_account", "") or "").lower(),
            ]
            combined = " ".join(fields_to_check)

            for pattern in CRYPTO_MERCHANT_PATTERNS:
                if pattern in combined:
                    crypto_hits += 1
                    break

            for pattern in GAMING_MERCHANT_PATTERNS:
                if pattern in combined:
                    gaming_hits += 1
                    break

        total = len(txns)
        if total == 0:
            return 0.0

        crypto_ratio = crypto_hits / total
        gaming_ratio = gaming_hits / total

        score = 0.0
        if crypto_hits >= 3:
            score = min(1.0, 0.5 + crypto_ratio)
        elif crypto_hits >= 1:
            score = 0.4

        if gaming_hits >= 3:
            score = max(score, min(1.0, 0.4 + gaming_ratio))
        elif gaming_hits >= 1:
            score = max(score, 0.3)

        return score
