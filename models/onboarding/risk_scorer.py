"""
Onboarding Risk Scorer
=======================
Assesses mule risk at the point of account onboarding — before any
transactional history exists. Fills the gap identified in Problem
Statement #2: "detection during onboarding as well as post-onboarding."

14 signal scorers evaluate KYC completeness, device fingerprints,
geolocation, identity verification speed, and behavioral indicators.

Returns an immutable OnboardingRiskResult dataclass.
"""

from __future__ import annotations

import math
import uuid
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# ── Risk level thresholds ────────────────────────────────────────────────────

RISK_LOW = "LOW"
RISK_MEDIUM = "MEDIUM"
RISK_HIGH = "HIGH"
RISK_CRITICAL = "CRITICAL"


def _risk_level(score: float) -> str:
    if score >= 0.70:
        return RISK_CRITICAL
    if score >= 0.50:
        return RISK_HIGH
    if score >= 0.30:
        return RISK_MEDIUM
    return RISK_LOW


RECOMMENDATIONS = {
    RISK_LOW: "APPROVE — low onboarding risk",
    RISK_MEDIUM: "APPROVE_WITH_MONITORING — enhanced transaction monitoring recommended",
    RISK_HIGH: "MANUAL_REVIEW — require supervisor approval before activation",
    RISK_CRITICAL: "BLOCK — auto-reject or escalate to AML team",
}


# ── Result dataclass (frozen = immutable) ────────────────────────────────────


@dataclass(frozen=True)
class OnboardingRiskResult:
    assessment_id: str
    account_id: str
    risk_score: float
    risk_level: str
    signals: Tuple[Dict, ...]  # frozen-compatible
    reason_codes: Tuple[str, ...]
    recommendation: str
    assessed_at: str


# ── Signal weights ───────────────────────────────────────────────────────────

SIGNAL_WEIGHTS: Dict[str, float] = {
    "account_age": 0.10,
    "kyc_completeness": 0.08,
    "document_verification_speed": 0.06,
    "device_fingerprint_overlap": 0.08,
    "ip_geolocation_mismatch": 0.08,
    "phone_number_age": 0.06,
    "email_age": 0.06,
    "address_verification": 0.05,
    "selfie_match": 0.08,
    "application_velocity": 0.07,
    "similar_name_accounts": 0.05,
    "high_risk_geography": 0.05,
    "nocturnal_application": 0.04,
    "dormancy_after_onboarding": 0.06,
    "graph_cross_check": 0.08,
}


# ── Individual signal scorers (each returns 0.0 – 1.0) ──────────────────────


def _score_account_age(days: float) -> float:
    """New accounts (<7d) score high; >90d score near zero."""
    if days <= 0:
        return 1.0
    if days >= 90:
        return 0.0
    # Exponential decay: 7-day half-life
    return min(1.0, math.exp(-0.1 * days))


def _score_kyc_completeness(ratio: float) -> float:
    """KYC completeness ratio 0.0-1.0. Lower = higher risk."""
    ratio = max(0.0, min(1.0, ratio))
    return 1.0 - ratio


def _score_document_verification_speed(seconds: float) -> float:
    """Suspiciously fast verification (<30s) suggests automation/bot."""
    if seconds <= 0:
        return 1.0
    if seconds >= 300:
        return 0.0
    if seconds < 30:
        return 0.95
    if seconds < 60:
        return 0.7
    # Gradual decline
    return max(0.0, 1.0 - (seconds / 300))


def _score_device_fingerprint_overlap(count: int) -> float:
    """Device shared with N flagged accounts. More overlap = higher risk."""
    if count <= 0:
        return 0.0
    if count >= 5:
        return 1.0
    return min(1.0, count * 0.25)


def _score_ip_geolocation_mismatch(mismatch: bool) -> float:
    """IP location doesn't match declared residential address."""
    return 0.85 if mismatch else 0.0


def _score_phone_number_age(days: float) -> float:
    """Recently activated phone numbers are riskier."""
    if days <= 0:
        return 0.9
    if days >= 365:
        return 0.0
    if days < 30:
        return 0.8
    if days < 90:
        return 0.5
    return max(0.0, 1.0 - (days / 365))


def _score_email_age(days: float) -> float:
    """Recently created email addresses are riskier."""
    if days <= 0:
        return 0.85
    if days >= 365:
        return 0.0
    if days < 7:
        return 0.8
    if days < 30:
        return 0.6
    return max(0.0, 1.0 - (days / 365))


def _score_address_verification(verified: bool) -> float:
    """Address not verified = higher risk."""
    return 0.0 if verified else 0.7


def _score_selfie_match(confidence: float) -> float:
    """Low selfie-document match confidence suggests identity fraud."""
    confidence = max(0.0, min(1.0, confidence))
    if confidence >= 0.95:
        return 0.0
    if confidence >= 0.80:
        return 0.3
    if confidence >= 0.60:
        return 0.6
    return 0.9


def _score_application_velocity(count: int) -> float:
    """Multiple applications from same device/IP in short window."""
    if count <= 1:
        return 0.0
    if count >= 5:
        return 1.0
    return min(1.0, (count - 1) * 0.3)


def _score_similar_name_accounts(count: int) -> float:
    """Name variants already in system — possible synthetic identity."""
    if count <= 0:
        return 0.0
    if count >= 4:
        return 1.0
    return min(1.0, count * 0.3)


def _score_high_risk_geography(is_high_risk: bool) -> float:
    """Applicant from FATF high-risk or IOB-flagged region."""
    return 0.8 if is_high_risk else 0.0


def _score_nocturnal_application(hour: int) -> float:
    """Applications submitted between 11PM-5AM are unusual."""
    if 23 <= hour or hour < 5:
        return 0.7
    return 0.0


def _score_dormancy_after_onboarding(days_inactive: float, total_days: float) -> float:
    """Account opened but no activity — parked for future mule use."""
    if total_days <= 7:
        return 0.0  # too new to judge
    if days_inactive <= 0:
        return 0.0
    ratio = days_inactive / max(total_days, 1)
    if ratio >= 0.9:
        return 0.85
    if ratio >= 0.7:
        return 0.6
    if ratio >= 0.5:
        return 0.4
    return 0.0


def _score_graph_cross_check(flagged_count: int, cluster_count: int = 0) -> float:
    """Device/IP/phone linked to known mule cluster accounts in graph."""
    if flagged_count <= 0:
        return 0.0
    if flagged_count >= 5:
        return 1.0
    score = min(1.0, flagged_count * 0.25)
    # Boost if connected to multiple clusters
    if cluster_count >= 2:
        score = min(1.0, score + 0.15)
    return score


# ── Reason code mappings ────────────────────────────────────────────────────

REASON_CODES = {
    "account_age": ("OB01", "Account age < 7 days"),
    "kyc_completeness": ("OB02", "KYC completeness below threshold"),
    "document_verification_speed": ("OB03", "Document verification suspiciously fast"),
    "device_fingerprint_overlap": ("OB04", "Device shared with flagged accounts"),
    "ip_geolocation_mismatch": (
        "OB05",
        "IP geolocation mismatch with declared address",
    ),
    "phone_number_age": ("OB06", "Phone number recently activated"),
    "email_age": ("OB07", "Email address recently created"),
    "address_verification": ("OB08", "Address not verified"),
    "selfie_match": ("OB09", "Low selfie-document match confidence"),
    "application_velocity": ("OB10", "Multiple applications from same device/IP"),
    "similar_name_accounts": ("OB11", "Similar name variants found in system"),
    "high_risk_geography": ("OB12", "High-risk geographic region"),
    "nocturnal_application": ("OB13", "Application submitted during unusual hours"),
    "dormancy_after_onboarding": ("OB14", "Account dormant after onboarding"),
    "graph_cross_check": (
        "OB15",
        "Device/IP/phone linked to known mule cluster in graph",
    ),
}

# Threshold above which a signal generates a reason code
REASON_THRESHOLD = 0.3


# ── Helper functions ────────────────────────────────────────────────────────


def _get_graph_check_result(application: Dict, graph_checker=None):
    """Get flagged count and cluster count from graph checker or application data."""
    if graph_checker is not None:
        try:
            result = graph_checker(
                device_id=application.get("device_fingerprint"),
                ip_address=application.get("ip_address"),
                phone=application.get("phone_number"),
            )
            return (result.get("flagged_count", 0), len(result.get("cluster_ids", [])))
        except Exception:
            return (0, 0)
    # Fallback: use pre-computed values from application dict
    return (
        application.get("graph_flagged_count", 0),
        application.get("graph_cluster_count", 0),
    )


# ── Main assessment function ────────────────────────────────────────────────


def assess_onboarding_risk(
    application: Dict,
    graph_checker=None,
) -> OnboardingRiskResult:
    """
    Score an account application for mule risk.

    Parameters
    ----------
    application : dict
        Keys (all optional with safe defaults):
        - account_id, account_age_days, kyc_completeness (0-1),
        - doc_verification_seconds, device_overlap_count,
        - ip_geolocation_mismatch (bool), phone_age_days, email_age_days,
        - address_verified (bool), selfie_confidence (0-1),
        - application_velocity_count, similar_name_count,
        - high_risk_geography (bool), application_hour (0-23),
        - days_inactive, total_account_days

    Returns
    -------
    OnboardingRiskResult (frozen dataclass)
    """
    account_id = application.get("account_id", f"UNKNOWN_{uuid.uuid4().hex[:6]}")

    # Evaluate each signal
    raw_signals: List[Dict] = []

    signal_scores = {
        "account_age": _score_account_age(application.get("account_age_days", 30)),
        "kyc_completeness": _score_kyc_completeness(
            application.get("kyc_completeness", 1.0)
        ),
        "document_verification_speed": _score_document_verification_speed(
            application.get("doc_verification_seconds", 120)
        ),
        "device_fingerprint_overlap": _score_device_fingerprint_overlap(
            application.get("device_overlap_count", 0)
        ),
        "ip_geolocation_mismatch": _score_ip_geolocation_mismatch(
            application.get("ip_geolocation_mismatch", False)
        ),
        "phone_number_age": _score_phone_number_age(
            application.get("phone_age_days", 365)
        ),
        "email_age": _score_email_age(application.get("email_age_days", 365)),
        "address_verification": _score_address_verification(
            application.get("address_verified", True)
        ),
        "selfie_match": _score_selfie_match(application.get("selfie_confidence", 0.95)),
        "application_velocity": _score_application_velocity(
            application.get("application_velocity_count", 1)
        ),
        "similar_name_accounts": _score_similar_name_accounts(
            application.get("similar_name_count", 0)
        ),
        "high_risk_geography": _score_high_risk_geography(
            application.get("high_risk_geography", False)
        ),
        "nocturnal_application": _score_nocturnal_application(
            application.get("application_hour", 12)
        ),
        "dormancy_after_onboarding": _score_dormancy_after_onboarding(
            application.get("days_inactive", 0),
            application.get("total_account_days", 0),
        ),
        "graph_cross_check": _score_graph_cross_check(
            *_get_graph_check_result(application, graph_checker)
        ),
    }

    # Build signal details list
    for name, score in signal_scores.items():
        raw_signals.append(
            {
                "signal": name,
                "score": round(score, 3),
                "weight": SIGNAL_WEIGHTS[name],
                "weighted": round(score * SIGNAL_WEIGHTS[name], 4),
            }
        )

    # Weighted composite score
    composite = sum(
        signal_scores[name] * SIGNAL_WEIGHTS[name] for name in SIGNAL_WEIGHTS
    )
    # Normalize to 0-1 (weights already sum to ~1.0 but cap for safety)
    weight_total = sum(SIGNAL_WEIGHTS.values())
    risk_score = min(composite / weight_total, 0.99)
    risk_score = round(risk_score, 4)

    # Risk level
    level = _risk_level(risk_score)

    # Reason codes for triggered signals
    reason_codes: List[str] = []
    for name, score in signal_scores.items():
        if score >= REASON_THRESHOLD and name in REASON_CODES:
            code, desc = REASON_CODES[name]
            reason_codes.append(f"{code}: {desc} (score={score:.2f})")

    recommendation = RECOMMENDATIONS[level]

    logger.info(
        "Onboarding risk assessed: account=%s score=%.4f level=%s signals=%d",
        account_id,
        risk_score,
        level,
        len(reason_codes),
    )

    return OnboardingRiskResult(
        assessment_id=f"OBA-{uuid.uuid4().hex[:8].upper()}",
        account_id=account_id,
        risk_score=risk_score,
        risk_level=level,
        signals=tuple(raw_signals),
        reason_codes=tuple(reason_codes),
        recommendation=recommendation,
        assessed_at=datetime.now(timezone.utc).isoformat(),
    )
