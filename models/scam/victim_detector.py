"""
Scam Victim Detector — Sender-Side Risk Scoring
==================================================
Detects potential scam victims who are being coached into sending money
to mule accounts. Inspired by Feedzai ScamPrevent and UK PSR regulations.

Signals:
  SV01 — Active call during transaction
  SV02 — Coached session behavior (backspaces, paste, app-switching)
  SV03 — Unusual beneficiary + unusual amount
  SV04 — Urgency indicators (rapid navigation, skipped balance check)
  SV05 — Age/vulnerability correlation
  SV06 — Known scam script keyword patterns
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Scam keywords found in transaction narrations
SCAM_KEYWORDS: Tuple[str, ...] = (
    "safe account",
    "rbi verification",
    "insurance claim",
    "tax refund",
    "customs",
    "lottery",
    "prize",
    "arrest warrant",
    "money laundering investigation",
)


@dataclass(frozen=True)
class ScamVictimResult:
    """Immutable result of scam victim detection."""

    account_id: str
    victim_probability: float  # 0.0-1.0
    coaching_indicators: Tuple[str, ...]
    session_anomalies: Tuple[str, ...]
    recommended_intervention: str  # NONE, SOFT_WARNING, HARD_WARNING, DELAY, BLOCK
    reason_codes: Tuple[str, ...]
    composite_score: float
    score_breakdown: Dict[str, float]


class ScamVictimDetector:
    """Detects potential scam victims on the sender side.

    Evaluates six independent signals (SV01-SV06), each producing a
    0.0-1.0 score. A weighted composite determines the final victim
    probability and recommended intervention level.
    """

    WEIGHTS: Dict[str, float] = {
        "active_call": 0.20,
        "coached_behavior": 0.20,
        "unusual_beneficiary_amount": 0.20,
        "urgency_indicators": 0.15,
        "vulnerability": 0.10,
        "scam_keywords": 0.15,
    }

    def detect(
        self,
        account_id: str,
        transaction: Dict,
        session_context: Optional[Dict] = None,
        account_history: Optional[List[Dict]] = None,
    ) -> ScamVictimResult:
        """Run all scam victim signals and return a composite result.

        Parameters
        ----------
        account_id : str
            The sender's account identifier.
        transaction : dict
            Current transaction details (amount, narration, is_new_beneficiary, etc.).
        session_context : dict, optional
            Real-time session telemetry (phone call, backspaces, app switches, etc.).
        account_history : list[dict], optional
            Historical transactions for the sender account.
        """
        ctx = session_context or {}
        history = account_history or []
        account = transaction.get("account", {})

        coaching_indicators: List[str] = []
        session_anomalies: List[str] = []
        reason_codes: List[str] = []
        breakdown: Dict[str, float] = {}

        # --- SV01: Active call during transaction ---
        sv01 = self._score_active_call(transaction, ctx)
        breakdown["active_call"] = sv01
        if sv01 > 0.0:
            coaching_indicators.append("SV01: On phone call during transfer")
            reason_codes.append("SV01_ACTIVE_CALL")

        # --- SV02: Coached session behavior ---
        sv02 = self._score_coached_behavior(ctx)
        breakdown["coached_behavior"] = sv02
        if sv02 > 0.0:
            indicators = self._get_coaching_details(ctx)
            coaching_indicators.extend(indicators)
            session_anomalies.extend(indicators)
            reason_codes.append("SV02_COACHED_BEHAVIOR")

        # --- SV03: Unusual beneficiary + amount ---
        sv03 = self._score_unusual_beneficiary_amount(transaction, history)
        breakdown["unusual_beneficiary_amount"] = sv03
        if sv03 > 0.0:
            reason_codes.append("SV03_UNUSUAL_BENEFICIARY_AMOUNT")

        # --- SV04: Urgency indicators ---
        sv04 = self._score_urgency(ctx)
        breakdown["urgency_indicators"] = sv04
        if sv04 > 0.0:
            urgency_details = self._get_urgency_details(ctx)
            session_anomalies.extend(urgency_details)
            reason_codes.append("SV04_URGENCY")

        # --- SV05: Vulnerability (age) ---
        sv05 = self._score_vulnerability(account, transaction)
        breakdown["vulnerability"] = sv05
        if sv05 > 0.0:
            reason_codes.append("SV05_ELDERLY_VULNERABILITY")

        # --- SV06: Scam keywords ---
        sv06 = self._score_scam_keywords(transaction)
        breakdown["scam_keywords"] = sv06
        if sv06 > 0.0:
            reason_codes.append("SV06_SCAM_KEYWORDS")

        # --- Composite score ---
        composite = sum(self.WEIGHTS[signal] * score for signal, score in breakdown.items())
        composite = round(min(max(composite, 0.0), 1.0), 4)

        intervention = self._map_intervention(composite)

        return ScamVictimResult(
            account_id=account_id,
            victim_probability=composite,
            coaching_indicators=tuple(coaching_indicators),
            session_anomalies=tuple(session_anomalies),
            recommended_intervention=intervention,
            reason_codes=tuple(reason_codes),
            composite_score=composite,
            score_breakdown=breakdown,
        )

    # ── Signal Scoring Methods ──────────────────────────────────────────

    @staticmethod
    def _score_active_call(transaction: Dict, ctx: Dict) -> float:
        """SV01: Active phone call during high-value transfer to new beneficiary."""
        if not ctx.get("on_phone_call", False):
            return 0.0
        amount = transaction.get("amount", 0)
        is_new = transaction.get("is_new_beneficiary", False)
        if amount > 50_000 and is_new:
            return 1.0
        if amount > 50_000 or is_new:
            return 0.6
        return 0.3

    @staticmethod
    def _score_coached_behavior(ctx: Dict) -> float:
        """SV02: Coached session indicators — backspaces, copy-paste, app-switching."""
        indicator_count = 0
        if ctx.get("backspace_count", 0) > 10:
            indicator_count += 1
        if ctx.get("amount_pasted", False):
            indicator_count += 1
        if ctx.get("app_switch_count", 0) > 3:
            indicator_count += 1

        if indicator_count == 0:
            return 0.0
        if indicator_count == 1:
            return 0.4
        if indicator_count == 2:
            return 0.7
        return 1.0

    @staticmethod
    def _get_coaching_details(ctx: Dict) -> List[str]:
        """Return human-readable coaching indicator descriptions."""
        details: List[str] = []
        if ctx.get("backspace_count", 0) > 10:
            details.append("SV02: Excessive backspaces in amount field")
        if ctx.get("amount_pasted", False):
            details.append("SV02: Amount was copy-pasted")
        if ctx.get("app_switch_count", 0) > 3:
            details.append("SV02: Frequent app-switching during transfer")
        return details

    @staticmethod
    def _score_unusual_beneficiary_amount(
        transaction: Dict,
        history: List[Dict],
    ) -> float:
        """SV03: First-time recipient + amount exceeds 3x historical average."""
        is_new = transaction.get("is_new_beneficiary", False)
        if not is_new:
            return 0.0

        amount = transaction.get("amount", 0)
        if not history:
            # No history — new beneficiary alone is mild signal
            return 0.4 if is_new else 0.0

        avg_amount = sum(t.get("amount", 0) for t in history) / len(history)
        if avg_amount > 0 and amount > 3 * avg_amount:
            return 1.0
        if avg_amount > 0 and amount > 2 * avg_amount:
            return 0.6
        return 0.3

    @staticmethod
    def _score_urgency(ctx: Dict) -> float:
        """SV04: Urgency — rapid navigation, skipped balance check."""
        score = 0.0
        time_to_transfer = ctx.get("time_to_transfer_seconds", 999)
        if time_to_transfer < 30:
            score += 0.6
        elif time_to_transfer < 60:
            score += 0.3

        if not ctx.get("checked_balance", True):
            score += 0.4

        return min(score, 1.0)

    @staticmethod
    def _score_vulnerability(account: Dict, transaction: Dict) -> float:
        """SV05: Elderly or vulnerable sender with large transfer to unknown."""
        age = account.get("account_holder_age", 0)
        if age < 60:
            return 0.0
        is_new = transaction.get("is_new_beneficiary", False)
        amount = transaction.get("amount", 0)
        if is_new and amount > 50_000:
            return 1.0
        if is_new or amount > 50_000:
            return 0.6
        return 0.3

    @staticmethod
    def _score_scam_keywords(transaction: Dict) -> float:
        """SV06: Known scam script patterns in transaction narration."""
        narration = transaction.get("narration", "").lower()
        if not narration:
            return 0.0
        matches = sum(1 for kw in SCAM_KEYWORDS if kw in narration)
        if matches >= 2:
            return 1.0
        if matches == 1:
            return 0.8
        return 0.0

    @staticmethod
    def _map_intervention(score: float) -> str:
        """Map composite score to recommended intervention level."""
        if score >= 0.8:
            return "BLOCK"
        if score >= 0.6:
            return "DELAY"
        if score >= 0.4:
            return "HARD_WARNING"
        if score >= 0.2:
            return "SOFT_WARNING"
        return "NONE"

    @staticmethod
    def _get_urgency_details(ctx: Dict) -> List[str]:
        """Return human-readable urgency indicator descriptions."""
        details: List[str] = []
        time_to_transfer = ctx.get("time_to_transfer_seconds", 999)
        if time_to_transfer < 30:
            details.append("SV04: Rapid navigation to transfer (< 30s)")
        elif time_to_transfer < 60:
            details.append("SV04: Fast navigation to transfer (< 60s)")
        if not ctx.get("checked_balance", True):
            details.append("SV04: Skipped balance check before transfer")
        return details
