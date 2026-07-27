"""
MuleCatch Mule Type Classifier
================================
Classifies detected mule accounts into categories:
  - COMPLICIT  — Account holder knowingly participates
  - EXPLOITED  — Account holder is a victim (social engineering, etc.)
  - UNKNOWN    — Insufficient evidence to determine

Based on BioCatch research: 48% of mule accounts show behavioral
inconsistencies within 72 hours of account opening.

Signals used:
  - Account age and KYC status
  - Transaction velocity and patterns
  - Device sharing evidence
  - Time-of-day patterns
  - Fund retention duration
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

# ── Scoring weights (tunable constants) ────────────────────────────────────
# Account age signals
WEIGHT_AGE_VERY_NEW = 0.20  # < 7 days → complicit
WEIGHT_AGE_NEW = 0.10  # < 30 days → complicit
WEIGHT_AGE_ESTABLISHED = 0.15  # > 365 days → exploited

# KYC signals
WEIGHT_KYC_PENDING = 0.10  # KYC incomplete → complicit
WEIGHT_KYC_VERIFIED = 0.05  # KYC verified → exploited

# Device sharing
WEIGHT_DEVICE_SHARED = 0.25  # Shared device with flagged accounts

# Transaction patterns
WEIGHT_PASSTHROUGH_HIGH = 0.15  # > 90% pass-through ratio
WEIGHT_PASSTHROUGH_MED = 0.08  # > 70% pass-through ratio

# Night-time activity
WEIGHT_NIGHT_ACTIVITY = 0.10  # Transactions between 11PM-5AM

# Velocity burst (BioCatch 72-hour indicator)
WEIGHT_VELOCITY_BURST = 0.20  # High activity within 72h of opening
WEIGHT_DORMANT_REACTIVATION = 0.20  # Dormant account suddenly active

# Network role
WEIGHT_ROLE_SOURCE = 0.10  # Fund originator
WEIGHT_ROLE_AGGREGATOR = 0.15  # Terminal collection point

# Thresholds
THRESHOLD_PASSTHROUGH_HIGH = 0.90
THRESHOLD_PASSTHROUGH_MED = 0.70
THRESHOLD_AGE_VERY_NEW = 7  # days
THRESHOLD_AGE_NEW = 30  # days
THRESHOLD_AGE_ESTABLISHED = 365  # days
THRESHOLD_NIGHT_TXN_COUNT = 3  # min night-time transactions to flag
THRESHOLD_VELOCITY_BURST_DAYS = 3  # days since opening
THRESHOLD_VELOCITY_BURST_TXN = 5  # min outgoing transactions
THRESHOLD_DORMANT_DAYS = 180  # days to consider dormant
THRESHOLD_DORMANT_REACTIVATION_TXN = 10  # min outgoing for reactivation

# Classification decision thresholds
THRESHOLD_MIN_TOTAL_SCORE = 0.15  # below → UNKNOWN
THRESHOLD_CLASSIFICATION_RATIO = 1.3  # score must exceed other by this factor

# CBS behavioral weights
WEIGHT_CBS_PASSTHROUGH = 0.15  # CBS pass-through ratio >= 90%
WEIGHT_NEG_BALANCE_HIGH = 0.15  # >= 10 negative balance events
WEIGHT_NEG_BALANCE_MED = 0.08  # >= 3 negative balance events
WEIGHT_DC_RATIO_MATCH = 0.10  # debit/credit ratio near 1.0
WEIGHT_CREDIT_HUB = 0.15  # >= 50 incoming credits
WEIGHT_CREDIT_FUNNEL = 0.10  # >= 20 incoming credits

# CBS behavioral thresholds
THRESHOLD_CBS_PASSTHROUGH = 0.90
THRESHOLD_DC_RATIO_LOW = 0.85
THRESHOLD_DC_RATIO_HIGH = 1.15
THRESHOLD_NEG_BALANCE_HIGH = 10
THRESHOLD_NEG_BALANCE_MED = 3
THRESHOLD_CREDIT_HUB = 50
THRESHOLD_CREDIT_FUNNEL = 20

# Classification confidence bounds
CONFIDENCE_UNKNOWN = 0.3
CONFIDENCE_AMBIGUOUS = 0.5
CONFIDENCE_CAP = 0.95


@dataclass(frozen=True)
class MuleClassification:
    account_id: str
    classification: str  # COMPLICIT | EXPLOITED | UNKNOWN
    confidence: float
    reasoning: str
    signals: List[str]

    def to_dict(self) -> Dict:
        return {
            "account_id": self.account_id,
            "classification": self.classification,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "signals": self.signals,
        }


def classify_mule_type(
    account: Dict,
    transactions: List[Dict],
    shared_devices: Optional[List[str]] = None,
) -> MuleClassification:
    account_id = account.get("account_id", "")
    age_days = account.get("account_age_days", 365)
    kyc_status = account.get("kyc_status", "UNKNOWN")
    role = account.get("role", "UNKNOWN")

    complicit_score = 0.0
    exploited_score = 0.0
    signals = []

    # Signal 1: Account age
    if age_days < THRESHOLD_AGE_VERY_NEW:
        complicit_score += WEIGHT_AGE_VERY_NEW
        signals.append("Account opened <7 days ago - likely opened for fraud purpose")
    elif age_days < THRESHOLD_AGE_NEW:
        complicit_score += WEIGHT_AGE_NEW
        signals.append("Account opened <30 days ago - newly created")
    elif age_days > THRESHOLD_AGE_ESTABLISHED:
        exploited_score += WEIGHT_AGE_ESTABLISHED
        signals.append("Established account (>1 year) - may have been compromised")

    # Signal 2: KYC status
    if kyc_status == "PENDING":
        complicit_score += WEIGHT_KYC_PENDING
        signals.append("KYC incomplete - avoidance of identity verification")
    elif kyc_status == "VERIFIED":
        exploited_score += WEIGHT_KYC_VERIFIED
        signals.append("KYC fully verified - legitimate account holder")

    # Signal 3: Device sharing
    if shared_devices:
        acct_devices = set()
        for t in transactions:
            if t.get("from_account") == account_id and t.get("device_id"):
                acct_devices.add(t["device_id"])

        shared_count = sum(1 for d in acct_devices if d in shared_devices)
        if shared_count > 0:
            complicit_score += WEIGHT_DEVICE_SHARED
            signals.append(
                f"Device shared with {shared_count} other flagged account(s) "
                f"- coordinated operation"
            )

    # Signal 4: Transaction patterns
    outgoing = [t for t in transactions if t.get("from_account") == account_id]
    incoming = [t for t in transactions if t.get("to_account") == account_id]

    if outgoing and incoming:
        total_in = sum(float(t.get("amount", 0)) for t in incoming)
        total_out = sum(float(t.get("amount", 0)) for t in outgoing)
        if total_in > 0:
            passthrough_ratio = total_out / total_in
            if passthrough_ratio > THRESHOLD_PASSTHROUGH_HIGH:
                complicit_score += WEIGHT_PASSTHROUGH_HIGH
                signals.append(
                    f"Pass-through ratio {passthrough_ratio:.0%} - "
                    f"account used purely as conduit"
                )
            elif passthrough_ratio > THRESHOLD_PASSTHROUGH_MED:
                complicit_score += WEIGHT_PASSTHROUGH_MED
                signals.append(f"High forwarding ratio ({passthrough_ratio:.0%})")

    # Signal 5: Night-time activity
    night_txn_count = 0
    for t in outgoing:
        ts = t.get("timestamp", "")
        if isinstance(ts, str) and len(ts) > 13:
            hour = int(ts[11:13])
            if hour >= 23 or hour < 5:
                night_txn_count += 1
    if night_txn_count >= THRESHOLD_NIGHT_TXN_COUNT:
        complicit_score += WEIGHT_NIGHT_ACTIVITY
        signals.append(
            f"{night_txn_count} transactions between 11PM-5AM - "
            f"deliberate timing to avoid detection"
        )

    # Signal 6: Velocity burst (BioCatch 72-hour indicator)
    if (
        age_days <= THRESHOLD_VELOCITY_BURST_DAYS
        and len(outgoing) >= THRESHOLD_VELOCITY_BURST_TXN
    ):
        complicit_score += WEIGHT_VELOCITY_BURST
        signals.append(
            "High activity within 72 hours of account opening - "
            "BioCatch indicator for complicit mules"
        )
    elif (
        age_days > THRESHOLD_DORMANT_DAYS
        and len(outgoing) >= THRESHOLD_DORMANT_REACTIVATION_TXN
    ):
        exploited_score += WEIGHT_DORMANT_REACTIVATION
        signals.append(
            "Dormant account suddenly reactivated with high volume - "
            "likely account takeover or social engineering"
        )

    # Signal 7: Role in network
    if role == "SOURCE":
        complicit_score += WEIGHT_ROLE_SOURCE
        signals.append("Acts as fund originator in the mule network")
    elif role == "AGGREGATOR":
        complicit_score += WEIGHT_ROLE_AGGREGATOR
        signals.append("Acts as fund aggregator - terminal collection point")

    # Signal 8: CBS behavioral features (compensate for missing device/IP)
    cbs_pt = account.get("pass_through_ratio", 0.0)
    if cbs_pt >= THRESHOLD_CBS_PASSTHROUGH:
        complicit_score += WEIGHT_CBS_PASSTHROUGH
        signals.append(f"CBS pass-through ratio {cbs_pt:.0%} - same-day in/out pattern")

    neg_bal = account.get("negative_balance_count", 0)
    if neg_bal >= THRESHOLD_NEG_BALANCE_HIGH:
        exploited_score += WEIGHT_NEG_BALANCE_HIGH
        signals.append(
            f"{neg_bal} negative balance events - overdraft abuse (account exploitation)"
        )
    elif neg_bal >= THRESHOLD_NEG_BALANCE_MED:
        exploited_score += WEIGHT_NEG_BALANCE_MED
        signals.append(f"{neg_bal} negative balance events")

    dc_ratio = account.get("debit_credit_ratio", 0.0)
    if THRESHOLD_DC_RATIO_LOW <= dc_ratio <= THRESHOLD_DC_RATIO_HIGH and dc_ratio > 0:
        complicit_score += WEIGHT_DC_RATIO_MATCH
        signals.append(
            f"Debit/credit ratio {dc_ratio:.2f} - money in equals money out (pass-through)"
        )

    credit_count = account.get("credit_count", 0)
    if credit_count >= THRESHOLD_CREDIT_HUB:
        complicit_score += WEIGHT_CREDIT_HUB
        signals.append(f"{credit_count} incoming credits - collection hub pattern")
    elif credit_count >= THRESHOLD_CREDIT_FUNNEL:
        complicit_score += WEIGHT_CREDIT_FUNNEL
        signals.append(f"{credit_count} incoming credits - receiving funnel")

    # Classification decision
    total = complicit_score + exploited_score
    if total < THRESHOLD_MIN_TOTAL_SCORE:
        return MuleClassification(
            account_id=account_id,
            classification="UNKNOWN",
            confidence=CONFIDENCE_UNKNOWN,
            reasoning="Insufficient behavioral signals to determine mule type.",
            signals=signals,
        )

    if complicit_score > exploited_score * THRESHOLD_CLASSIFICATION_RATIO:
        confidence = min(complicit_score / max(total, 0.01), CONFIDENCE_CAP)
        reasoning = (
            f"Account shows {len([s for s in signals if 'complicit' in s.lower() or 'coordinated' in s.lower() or 'conduit' in s.lower() or 'deliberate' in s.lower()])} "
            f"strong indicators of knowing participation: "
            + "; ".join(signals[:3])
            + "."
        )
        return MuleClassification(
            account_id=account_id,
            classification="COMPLICIT",
            confidence=round(confidence, 2),
            reasoning=reasoning,
            signals=signals,
        )
    elif exploited_score > complicit_score * THRESHOLD_CLASSIFICATION_RATIO:
        confidence = min(exploited_score / max(total, 0.01), CONFIDENCE_CAP)
        reasoning = (
            "Account profile suggests the holder may be a victim: "
            + "; ".join(signals[:3])
            + "."
        )
        return MuleClassification(
            account_id=account_id,
            classification="EXPLOITED",
            confidence=round(confidence, 2),
            reasoning=reasoning,
            signals=signals,
        )
    else:
        return MuleClassification(
            account_id=account_id,
            classification="UNKNOWN",
            confidence=CONFIDENCE_AMBIGUOUS,
            reasoning=(
                f"Mixed signals prevent definitive classification. "
                f"Complicit indicators ({complicit_score:.2f}) vs "
                f"exploited indicators ({exploited_score:.2f}). "
                f"Manual review recommended."
            ),
            signals=signals,
        )


def classify_cluster(
    alert: Dict,
    transactions: List[Dict],
) -> Dict:
    nodes = alert.get("nodes", [])
    shared_devices = alert.get("shared_devices", [])

    classifications = []
    complicit_count = 0
    exploited_count = 0
    unknown_count = 0

    for node in nodes:
        account = node if isinstance(node, dict) else vars(node)
        result = classify_mule_type(account, transactions, shared_devices)
        classifications.append(result.to_dict())

        if result.classification == "COMPLICIT":
            complicit_count += 1
        elif result.classification == "EXPLOITED":
            exploited_count += 1
        else:
            unknown_count += 1

    total = len(nodes) or 1
    if complicit_count > exploited_count:
        cluster_type = "COMPLICIT"
        cluster_reasoning = (
            f"{complicit_count}/{total} accounts ({round(complicit_count / total * 100)}%) "
            f"show complicit mule indicators. This appears to be a coordinated, "
            f"knowingly-operated mule network."
        )
    elif exploited_count > complicit_count:
        cluster_type = "EXPLOITED"
        cluster_reasoning = (
            f"{exploited_count}/{total} accounts ({round(exploited_count / total * 100)}%) "
            f"show signs of exploitation. Account holders may be victims of social "
            f"engineering or account takeover."
        )
    else:
        cluster_type = "MIXED"
        cluster_reasoning = (
            f"Mixed network: {complicit_count} complicit, {exploited_count} exploited, "
            f"{unknown_count} undetermined. Network may contain both willing "
            f"participants and victims."
        )

    return {
        "cluster_classification": cluster_type,
        "cluster_reasoning": cluster_reasoning,
        "account_classifications": classifications,
        "summary": {
            "complicit": complicit_count,
            "exploited": exploited_count,
            "unknown": unknown_count,
            "total": total,
        },
    }
