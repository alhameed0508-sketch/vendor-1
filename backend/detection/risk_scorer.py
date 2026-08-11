"""
MuleCatch Risk Scorer
=====================
Data-driven risk classification using configurable thresholds.

Version 2.0 improvements (based on validation findings):
- All thresholds externalized to core.config
- Stricter HIGH RISK classification (reduces false positives)
- Transaction volume signal added
- Improved decision boundary between MEDIUM and HIGH risk
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from core.config import get_settings


@dataclass
class RiskAssessment:
    """Risk assessment result with detailed scoring breakdown."""

    risk_level: str  # HIGH RISK | MEDIUM RISK | LOW RISK
    confidence: str  # HIGH | MEDIUM | LOW
    behavioral_signals: List[str]
    anomaly_signals: List[str]
    behavioral_count: int
    anomaly_count: int
    reason: str


def compute_behavioral_signals(account_features: Dict) -> List[str]:
    """
    Detect behavioral signals using configurable thresholds.

    Returns list of triggered signal names.
    """
    settings = get_settings()
    signals = []

    # Signal 1: High pass-through ratio
    passthrough_ratio = account_features.get("in_out_ratio", 0)
    if passthrough_ratio > settings.passthrough_threshold_high:
        signals.append("high_passthrough")

    # Signal 2: Round amounts
    round_amt_share = account_features.get("round_amt_share", 0)
    if round_amt_share > settings.round_amount_threshold:
        signals.append("round_amounts")

    # Signal 3: Velocity spike
    txn_velocity = account_features.get("txn_velocity", 0)
    if txn_velocity > settings.velocity_spike_threshold:
        signals.append("velocity_spike")

    # Signal 4: Negative balance pattern
    neg_balance_share = account_features.get("neg_balance_share", 0)
    if neg_balance_share > settings.negative_balance_threshold:
        signals.append("negative_balance")

    # Signal 5: High volume (NEW - addresses validation finding)
    txn_count = account_features.get("txn_count", 0)
    if txn_count > settings.high_volume_txn_threshold:
        signals.append("high_volume")

    return signals


def compute_anomaly_signals(account_features: Dict) -> List[str]:
    """
    Detect anomaly signals from unsupervised detection engines.

    Returns list of triggered anomaly detector names.

    Note: K-Means is excluded from signal count as it's less reliable
    than DBSCAN and Isolation Forest for classification purposes.
    It's still tracked for investigative purposes.
    """
    signals = []

    # DBSCAN outlier detection (primary)
    if account_features.get("dbscan_outlier", False):
        signals.append("dbscan_outlier")

    # Isolation Forest anomaly (primary)
    if account_features.get("iso_anomaly", False):
        signals.append("iso_forest")

    # K-Means cluster - tracked but not counted toward classification
    # (too many false positives in validation)
    # kmeans_cluster = account_features.get('kmeans_cluster', -1)
    # if kmeans_cluster == 0:
    #     signals.append('kmeans_high_risk_cluster')

    return signals


def classify_risk_level(behavioral_signals: List[str], anomaly_signals: List[str]) -> Tuple[str, str, str]:
    """
    Classify risk level using improved decision boundary.

    V2.0 changes:
    - HIGH RISK now requires either:
      (a) 2+ anomaly signals AND 2+ behavioral signals, OR
      (b) 1+ anomaly signal AND 3+ behavioral signals
    - MEDIUM RISK: 3+ behavioral OR 1+ anomaly (but not HIGH)
    - LOW RISK: everything else

    Returns: (risk_level, confidence, reasoning)
    """
    settings = get_settings()

    behavioral_count = len(behavioral_signals)
    anomaly_count = len(anomaly_signals)

    # HIGH RISK classification (stricter than v1.0)
    high_risk_path_a = (
        anomaly_count >= settings.risk_high_anomaly_min and behavioral_count >= settings.risk_high_behavioral_min
    )
    high_risk_path_b = (
        anomaly_count >= settings.risk_high_anomaly_alt and behavioral_count >= settings.risk_high_behavioral_alt
    )

    if high_risk_path_a or high_risk_path_b:
        confidence = "HIGH" if high_risk_path_a else "MEDIUM"
        reason = (
            f"Multiple detection engines agree: {anomaly_count} anomaly signals, "
            f"{behavioral_count} behavioral signals. Strong evidence of mule activity."
        )
        return ("HIGH RISK", confidence, reason)

    # MEDIUM RISK classification
    medium_risk_behavioral = behavioral_count >= settings.risk_medium_behavioral_min
    medium_risk_anomaly = anomaly_count >= settings.risk_medium_anomaly_min

    if medium_risk_behavioral or medium_risk_anomaly:
        confidence = "MEDIUM"
        if medium_risk_behavioral and medium_risk_anomaly:
            reason = (
                f"Partial signals detected: {behavioral_count} behavioral, "
                f"{anomaly_count} anomaly. Warrants investigation."
            )
        elif medium_risk_behavioral:
            reason = f"{behavioral_count} behavioral signals detected but weak anomaly evidence. Review recommended."
        else:
            reason = (
                f"Anomaly detected by {anomaly_count} engine(s) but limited behavioral signals. May be false positive."
            )
        return ("MEDIUM RISK", confidence, reason)

    # LOW RISK (default)
    reason = (
        f"Insufficient risk signals: {behavioral_count} behavioral, {anomaly_count} anomaly. "
        "No immediate action required."
    )
    return ("LOW RISK", "LOW", reason)


def assess_account_risk(account_features: Dict) -> RiskAssessment:
    """
    Main risk assessment function using configurable, data-driven logic.

    Args:
        account_features: Dictionary with account features including:
            - in_out_ratio (pass-through ratio)
            - round_amt_share (share of round amounts)
            - txn_velocity (transactions per day)
            - neg_balance_share (share of time with negative balance)
            - txn_count (total transaction count)
            - dbscan_outlier (bool)
            - iso_anomaly (bool)
            - kmeans_cluster (int)

    Returns:
        RiskAssessment with classification and detailed breakdown
    """
    # Detect signals
    behavioral_signals = compute_behavioral_signals(account_features)
    anomaly_signals = compute_anomaly_signals(account_features)

    # Classify risk level
    risk_level, confidence, reason = classify_risk_level(behavioral_signals, anomaly_signals)

    return RiskAssessment(
        risk_level=risk_level,
        confidence=confidence,
        behavioral_signals=behavioral_signals,
        anomaly_signals=anomaly_signals,
        behavioral_count=len(behavioral_signals),
        anomaly_count=len(anomaly_signals),
        reason=reason,
    )


def get_signal_descriptions() -> Dict[str, str]:
    """
    Get human-readable descriptions of all detection signals.

    Useful for reporting and explainability.
    """
    return {
        # Behavioral signals
        "high_passthrough": "High pass-through ratio (>90%) - funds received and immediately sent out",
        "round_amounts": "High share of round amounts (>70%) - indicates structured transactions",
        "velocity_spike": "Transaction velocity spike - unusual burst of activity",
        "negative_balance": "Frequent negative balance - overdraft abuse pattern",
        "high_volume": "High transaction volume (>500 txns) - possible mule hub account",
        # Anomaly signals
        "dbscan_outlier": "DBSCAN density-based outlier detection",
        "iso_forest": "Isolation Forest anomaly detection",
        "kmeans_high_risk_cluster": "K-Means clustering assigned to high-risk cluster",
    }
