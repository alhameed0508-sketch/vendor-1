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
    if age_days < 7:
        complicit_score += 0.20
        signals.append("Account opened <7 days ago - likely opened for fraud purpose")
    elif age_days < 30:
        complicit_score += 0.10
        signals.append("Account opened <30 days ago - newly created")
    elif age_days > 365:
        exploited_score += 0.15
        signals.append("Established account (>1 year) - may have been compromised")

    # Signal 2: KYC status
    if kyc_status == "PENDING":
        complicit_score += 0.10
        signals.append("KYC incomplete - avoidance of identity verification")
    elif kyc_status == "VERIFIED":
        exploited_score += 0.05
        signals.append("KYC fully verified - legitimate account holder")

    # Signal 3: Device sharing
    if shared_devices:
        acct_devices = set()
        for t in transactions:
            if t.get("from_account") == account_id and t.get("device_id"):
                acct_devices.add(t["device_id"])

        shared_count = sum(1 for d in acct_devices if d in shared_devices)
        if shared_count > 0:
            complicit_score += 0.25
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
            if passthrough_ratio > 0.90:
                complicit_score += 0.15
                signals.append(
                    f"Pass-through ratio {passthrough_ratio:.0%} - "
                    f"account used purely as conduit"
                )
            elif passthrough_ratio > 0.70:
                complicit_score += 0.08
                signals.append(f"High forwarding ratio ({passthrough_ratio:.0%})")

    # Signal 5: Night-time activity
    night_txn_count = 0
    for t in outgoing:
        ts = t.get("timestamp", "")
        if isinstance(ts, str) and len(ts) > 13:
            hour = int(ts[11:13])
            if hour >= 23 or hour < 5:
                night_txn_count += 1
    if night_txn_count >= 3:
        complicit_score += 0.10
        signals.append(
            f"{night_txn_count} transactions between 11PM-5AM - "
            f"deliberate timing to avoid detection"
        )

    # Signal 6: Velocity burst (BioCatch 72-hour indicator)
    if age_days <= 3 and len(outgoing) >= 5:
        complicit_score += 0.20
        signals.append(
            "High activity within 72 hours of account opening - "
            "BioCatch indicator for complicit mules"
        )
    elif age_days > 180 and len(outgoing) >= 10:
        exploited_score += 0.20
        signals.append(
            "Dormant account suddenly reactivated with high volume - "
            "likely account takeover or social engineering"
        )

    # Signal 7: Role in network
    if role == "SOURCE":
        complicit_score += 0.10
        signals.append("Acts as fund originator in the mule network")
    elif role == "AGGREGATOR":
        complicit_score += 0.15
        signals.append("Acts as fund aggregator - terminal collection point")

    # Classification decision
    total = complicit_score + exploited_score
    if total < 0.15:
        return MuleClassification(
            account_id=account_id,
            classification="UNKNOWN",
            confidence=0.3,
            reasoning="Insufficient behavioral signals to determine mule type.",
            signals=signals,
        )

    if complicit_score > exploited_score * 1.5:
        confidence = min(complicit_score / max(total, 0.01), 0.95)
        reasoning = (
            f"Account shows {len([s for s in signals if 'complicit' in s.lower() or 'coordinated' in s.lower() or 'conduit' in s.lower() or 'deliberate' in s.lower()])} "
            f"strong indicators of knowing participation: "
            + "; ".join(signals[:3]) + "."
        )
        return MuleClassification(
            account_id=account_id,
            classification="COMPLICIT",
            confidence=round(confidence, 2),
            reasoning=reasoning,
            signals=signals,
        )
    elif exploited_score > complicit_score * 1.5:
        confidence = min(exploited_score / max(total, 0.01), 0.95)
        reasoning = (
            f"Account profile suggests the holder may be a victim: "
            + "; ".join(signals[:3]) + "."
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
            confidence=round(0.5, 2),
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
            f"{complicit_count}/{total} accounts ({round(complicit_count/total*100)}%) "
            f"show complicit mule indicators. This appears to be a coordinated, "
            f"knowingly-operated mule network."
        )
    elif exploited_count > complicit_count:
        cluster_type = "EXPLOITED"
        cluster_reasoning = (
            f"{exploited_count}/{total} accounts ({round(exploited_count/total*100)}%) "
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
