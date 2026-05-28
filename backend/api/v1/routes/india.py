"""
India-specific routes — /api/v1/india/*
FRI mobile risk, Jan Dhan detection, crypto/gaming patterns, UPI compliance.
"""

import os
import sys

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from typing import Dict, List, Optional

# Ensure models/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from core.response import success_response, error_response
from middleware.auth import require_permission

from models.india.fri_scorer import FRIClient, FRIRiskLevel
from models.india.jan_dhan_detector import JanDhanDetector
from models.india.crypto_gaming_detector import CryptoGamingDetector
from models.india.upi_compliance import UPIComplianceMonitor


# ── Request schemas ──────────────────────────────────────────────────

class JanDhanAssessRequest(BaseModel):
    account: Dict = Field(..., description="Account metadata dict")
    transactions: List[Dict] = Field(default_factory=list, description="Transaction list")


class CryptoGamingAssessRequest(BaseModel):
    account: Dict = Field(..., description="Account metadata dict")
    transactions: List[Dict] = Field(default_factory=list, description="Transaction list")


class UPIComplianceRequest(BaseModel):
    account: Dict = Field(..., description="Account metadata dict")
    transactions: List[Dict] = Field(default_factory=list, description="Transaction list")


class ShouldDelayRequest(BaseModel):
    transaction: Dict = Field(..., description="The transaction to evaluate")
    account: Dict = Field(..., description="Account metadata dict")
    recent_transactions: List[Dict] = Field(
        default_factory=list, description="Recent transactions for context"
    )


# ── Singleton instances ──────────────────────────────────────────────

_fri_client = FRIClient(demo_mode=True)
_jan_dhan_detector = JanDhanDetector()
_crypto_gaming_detector = CryptoGamingDetector()
_upi_monitor = UPIComplianceMonitor()


# ── Route registration ───────────────────────────────────────────────

def register_india_routes(r: APIRouter, limiter: Limiter) -> None:
    """Register India-specific routes on the given router."""

    @r.get("/fri/{mobile_number}")
    @limiter.limit("30/minute")
    def fri_lookup(
        request: Request,
        mobile_number: str,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """FRI mobile risk lookup — query DoT FRI for mobile number risk."""
        result = _fri_client.query_mobile_risk(mobile_number)
        return success_response({
            "mobile_number": result.mobile_number,
            "risk_level": result.risk_level.value,
            "source": result.source,
            "citizen_reports": result.citizen_reports,
            "ncrp_complaints": result.ncrp_complaints,
            "last_updated": result.last_updated,
            "score": result.score,
        })

    @r.post("/jan-dhan/assess")
    @limiter.limit("30/minute")
    def jan_dhan_assess(
        request: Request,
        req: JanDhanAssessRequest,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """Assess a Jan Dhan / BSBDA account for mule risk signals."""
        result = _jan_dhan_detector.assess(req.account, req.transactions)
        return success_response({
            "account_id": result.account_id,
            "is_bsbda": result.is_bsbda,
            "activity_spike_score": result.activity_spike_score,
            "reason_codes": list(result.reason_codes),
            "composite_score": result.composite_score,
        })

    @r.post("/crypto-gaming/assess")
    @limiter.limit("30/minute")
    def crypto_gaming_assess(
        request: Request,
        req: CryptoGamingAssessRequest,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """Assess account for crypto, gaming, and hawala laundering patterns."""
        result = _crypto_gaming_detector.assess(req.account, req.transactions)
        return success_response({
            "account_id": result.account_id,
            "crypto_score": result.crypto_score,
            "gaming_score": result.gaming_score,
            "hawala_score": result.hawala_score,
            "composite_score": result.composite_score,
            "reason_codes": list(result.reason_codes),
            "flagged_merchants": list(result.flagged_merchants),
        })

    @r.post("/upi-compliance/{account_id}")
    @limiter.limit("30/minute")
    def upi_compliance_check(
        request: Request,
        account_id: str,
        req: UPIComplianceRequest,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """UPI compliance check for an account."""
        account = {**req.account, "account_id": account_id}
        result = _upi_monitor.assess(account, req.transactions)
        return success_response({
            "account_id": result.account_id,
            "annual_upi_credit": result.annual_upi_credit,
            "limit_proximity_pct": result.limit_proximity_pct,
            "cooling_period_applicable": result.cooling_period_applicable,
            "flags": list(result.flags),
            "composite_score": result.composite_score,
        })

    @r.post("/upi-compliance/should-delay")
    @limiter.limit("60/minute")
    def upi_should_delay(
        request: Request,
        req: ShouldDelayRequest,
        user: dict = Depends(require_permission("alerts:read")),
    ):
        """Recommend whether a UPI payment should be delayed for cooling period."""
        should_delay, reason = _upi_monitor.should_delay_payment(
            req.transaction, req.account, req.recent_transactions,
        )
        return success_response({
            "should_delay": should_delay,
            "reason": reason,
        })
