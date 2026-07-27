"""
FRI (Financial Fraud Risk Indicator) Integration
=================================================
Queries DoT's FRI API for mobile-number risk scoring.
In demo mode, returns deterministic mock results based on phone number patterns.

Signals:
  - Chakshu citizen complaint count
  - NCRP (National Cyber Crime Reporting Portal) complaint count
  - Composite risk level mapping
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class FRIRiskLevel(Enum):
    """Risk levels returned by the FRI API."""

    VERY_HIGH = "VERY_HIGH"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    CLEAN = "CLEAN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FRIResult:
    """Immutable result from an FRI mobile risk query."""

    mobile_number: str
    risk_level: FRIRiskLevel
    source: str  # "FRI_API" | "MOCK" | "UNAVAILABLE"
    citizen_reports: int  # Chakshu complaint count
    ncrp_complaints: int  # NCRP complaint count
    last_updated: str
    score: float  # 0.0-1.0 risk score


# Regex for Indian mobile numbers: 10 digits starting with 6-9
_INDIAN_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")

# Risk-level to score mapping
_RISK_SCORES = {
    FRIRiskLevel.VERY_HIGH: 0.95,
    FRIRiskLevel.HIGH: 0.75,
    FRIRiskLevel.MEDIUM: 0.50,
    FRIRiskLevel.LOW: 0.25,
    FRIRiskLevel.CLEAN: 0.05,
    FRIRiskLevel.UNKNOWN: 0.0,
}


def _validate_mobile(mobile_number: str) -> str:
    """Sanitise and validate an Indian mobile number.

    Strips whitespace, leading +91, and leading 0 before validating
    the 10-digit core number.  Returns the cleaned 10-digit string.
    """
    cleaned = mobile_number.strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    if cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    if cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]
    return cleaned


class FRIClient:
    """Client for the DoT FRI (Fraud Risk Indicator) API.

    In demo mode, returns deterministic mock results derived from the
    last four digits of the phone number:
      - 0000-0009  -> VERY_HIGH  (known fraud SIMs)
      - 1000-1999  -> HIGH
      - 2000-2999  -> MEDIUM
      - 3000-3999  -> LOW
      - everything else -> CLEAN
    """

    def __init__(self, demo_mode: bool = True, api_url: Optional[str] = None):
        self._demo_mode = demo_mode
        self._api_url = api_url or "https://fri.dot.gov.in/api/v1"

    # ── Public API ───────────────────────────────────────────────────

    def query_mobile_risk(self, mobile_number: str) -> FRIResult:
        """Query FRI risk for a mobile number.

        Returns a deterministic mock in demo mode.
        Falls back to UNKNOWN if the real API is unavailable.
        """
        cleaned = _validate_mobile(mobile_number)

        if not _INDIAN_MOBILE_RE.match(cleaned):
            return FRIResult(
                mobile_number=cleaned,
                risk_level=FRIRiskLevel.UNKNOWN,
                source="UNAVAILABLE",
                citizen_reports=0,
                ncrp_complaints=0,
                last_updated=datetime.now(timezone.utc).isoformat(),
                score=0.0,
            )

        if self._demo_mode:
            return self._mock_query(cleaned)

        return self._live_query(cleaned)

    # ── Mock implementation ──────────────────────────────────────────

    def _mock_query(self, mobile: str) -> FRIResult:
        """Deterministic mock based on last four digits."""
        last_four = int(mobile[-4:])
        now_iso = datetime.now(timezone.utc).isoformat()

        if last_four <= 9:
            level = FRIRiskLevel.VERY_HIGH
            citizen = 15 + last_four
            ncrp = 8 + last_four
        elif 1000 <= last_four <= 1999:
            level = FRIRiskLevel.HIGH
            citizen = 5 + (last_four - 1000) % 10
            ncrp = 2 + (last_four - 1000) % 5
        elif 2000 <= last_four <= 2999:
            level = FRIRiskLevel.MEDIUM
            citizen = 2 + (last_four - 2000) % 3
            ncrp = 1
        elif 3000 <= last_four <= 3999:
            level = FRIRiskLevel.LOW
            citizen = 1
            ncrp = 0
        else:
            level = FRIRiskLevel.CLEAN
            citizen = 0
            ncrp = 0

        return FRIResult(
            mobile_number=mobile,
            risk_level=level,
            source="MOCK",
            citizen_reports=citizen,
            ncrp_complaints=ncrp,
            last_updated=now_iso,
            score=_RISK_SCORES[level],
        )

    # ── Live API call (placeholder) ──────────────────────────────────

    def _live_query(self, mobile: str) -> FRIResult:
        """Call the real FRI API.  Gracefully falls back to UNKNOWN."""
        try:
            # In production, this would be an HTTP call to self._api_url
            logger.warning("FRI live API not yet integrated; returning UNKNOWN")
            return FRIResult(
                mobile_number=mobile,
                risk_level=FRIRiskLevel.UNKNOWN,
                source="UNAVAILABLE",
                citizen_reports=0,
                ncrp_complaints=0,
                last_updated=datetime.now(timezone.utc).isoformat(),
                score=0.0,
            )
        except Exception as exc:
            logger.error("FRI API call failed: %s", exc)
            return FRIResult(
                mobile_number=mobile,
                risk_level=FRIRiskLevel.UNKNOWN,
                source="UNAVAILABLE",
                citizen_reports=0,
                ncrp_complaints=0,
                last_updated=datetime.now(timezone.utc).isoformat(),
                score=0.0,
            )
