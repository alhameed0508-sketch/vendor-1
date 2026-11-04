"""
Dual Risk Engine — Sender + Receiver Transaction Evaluation
==============================================================
Evaluates both the sender (potential scam victim) and receiver (potential
mule) sides of a transaction to produce a combined risk assessment.

When *both* sides show elevated risk, it provides the highest confidence
signal — a coached victim is sending money to a known mule.

Intervention messages are contextual and scenario-based, inspired by
UK PSR scam prevention regulations and Feedzai ScamPrevent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from models.scam.victim_detector import ScamVictimDetector, ScamVictimResult

logger = logging.getLogger(__name__)

# Intervention messages keyed by scenario
_MESSAGES = {
    "scam_keywords": (
        "Are you being asked to move money to a 'safe account'? "
        "Banks never ask you to do this. Please hang up and call us "
        "at our official number."
    ),
    "active_call": (
        "Is someone on the phone telling you to transfer money urgently? Scammers do this. Please hang up and call us."
    ),
    "elderly": (
        "We've noticed this is an unusual transaction for your account. "
        "Would you like to speak with a bank representative before proceeding?"
    ),
    "default_high": (
        "This transaction has been flagged for your protection. Please verify the recipient before proceeding."
    ),
}


@dataclass(frozen=True)
class DualRiskResult:
    """Immutable result of dual-sided transaction risk evaluation."""

    sender_risk: ScamVictimResult
    receiver_risk: Dict  # mule probability, reason codes from existing pipeline
    combined_risk: float  # 0.0-1.0
    transaction_recommendation: str  # ALLOW, DELAY_30S, DELAY_1HR, BLOCK_WITH_EDUCATION, BLOCK_HARD
    intervention_message: str  # Contextual warning for the sender
    reason_codes: Tuple[str, ...]


class DualRiskEngine:
    """Evaluates transactions from both sender and receiver perspectives.

    Combines the sender-side scam victim score with the receiver-side
    mule score to produce a dual risk assessment. When both sides are
    elevated, an interaction boost raises combined confidence.
    """

    def __init__(self, victim_detector: Optional[ScamVictimDetector] = None):
        self._victim_detector = victim_detector or ScamVictimDetector()

    def evaluate_transaction(
        self,
        sender: Dict,
        receiver: Dict,
        transaction: Dict,
        session_context: Optional[Dict] = None,
        sender_history: Optional[List[Dict]] = None,
        receiver_mule_score: float = 0.0,
    ) -> DualRiskResult:
        """Score both sides of a transaction.

        Parameters
        ----------
        sender : dict
            Sender account information (account_holder_age, account_id, etc.).
        receiver : dict
            Receiver account information.
        transaction : dict
            Transaction details (amount, narration, is_new_beneficiary, etc.).
        session_context : dict, optional
            Real-time session telemetry for the sender.
        sender_history : list[dict], optional
            Sender's historical transactions.
        receiver_mule_score : float
            Mule probability from the existing detection pipeline (0.0-1.0).
        """
        # Enrich transaction with sender account info
        enriched_txn = {**transaction, "account": sender}
        sender_account_id = sender.get("account_id", "UNKNOWN")

        # 1. Score sender for victim indicators
        sender_result = self._victim_detector.detect(
            account_id=sender_account_id,
            transaction=enriched_txn,
            session_context=session_context,
            account_history=sender_history,
        )

        # 2. Build receiver risk dict from existing pipeline score
        receiver_risk = {
            "account_id": receiver.get("account_id", "UNKNOWN"),
            "mule_probability": receiver_mule_score,
            "reason_codes": receiver.get("reason_codes", []),
        }

        # 3. Combined risk with interaction boost
        sender_score = sender_result.composite_score
        interaction_boost = 1.0 if (sender_score > 0.5 and receiver_mule_score > 0.5) else 0.0
        combined = sender_score * 0.4 + receiver_mule_score * 0.4 + interaction_boost * 0.2
        combined = round(min(max(combined, 0.0), 1.0), 4)

        # 4. Map recommendation
        recommendation = self._map_recommendation(combined)

        # 5. Merge reason codes from both sides
        all_reason_codes = list(sender_result.reason_codes)
        if receiver_mule_score > 0.3:
            all_reason_codes.append("RECEIVER_MULE_ELEVATED")
        if interaction_boost > 0.0:
            all_reason_codes.append("DUAL_RISK_INTERACTION_BOOST")

        # 6. Generate intervention message
        intervention_msg = self.generate_intervention_message(
            sender_result,
            combined,
        )

        return DualRiskResult(
            sender_risk=sender_result,
            receiver_risk=receiver_risk,
            combined_risk=combined,
            transaction_recommendation=recommendation,
            intervention_message=intervention_msg,
            reason_codes=tuple(all_reason_codes),
        )

    def generate_intervention_message(
        self,
        sender_result: ScamVictimResult,
        combined_risk: float,
    ) -> str:
        """Generate a contextual warning message for the sender.

        Selects the most relevant message based on which signals fired.
        Returns an empty string for low-risk transactions.
        """
        if combined_risk < 0.2:
            return ""

        reason_set = set(sender_result.reason_codes)

        # Priority order: scam keywords > active call > elderly > default
        if "SV06_SCAM_KEYWORDS" in reason_set:
            return _MESSAGES["scam_keywords"]
        if "SV01_ACTIVE_CALL" in reason_set:
            return _MESSAGES["active_call"]
        if "SV05_ELDERLY_VULNERABILITY" in reason_set:
            return _MESSAGES["elderly"]
        return _MESSAGES["default_high"]

    @staticmethod
    def _map_recommendation(combined: float) -> str:
        """Map combined risk to a transaction recommendation."""
        if combined >= 0.8:
            return "BLOCK_HARD"
        if combined >= 0.6:
            return "BLOCK_WITH_EDUCATION"
        if combined >= 0.4:
            return "DELAY_1HR"
        if combined >= 0.25:
            return "DELAY_30S"
        return "ALLOW"
