"""
Onboarding risk assessment request schemas.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class OnboardingAssessRequest(BaseModel):
    """Single account onboarding risk assessment input."""
    account_id: str = Field("", max_length=100)
    account_age_days: int = Field(0, ge=0)
    kyc_completeness: float = Field(0.0, ge=0.0, le=1.0)
    doc_verification_seconds: float = Field(0.0, ge=0.0)
    device_overlap_count: int = Field(0, ge=0)
    ip_geolocation_mismatch: bool = False
    phone_age_days: int = Field(0, ge=0)
    email_age_days: int = Field(0, ge=0)
    address_verified: bool = False
    selfie_confidence: float = Field(0.0, ge=0.0, le=1.0)
    application_velocity_count: int = Field(0, ge=0)
    similar_name_count: int = Field(0, ge=0)
    high_risk_geography: bool = False
    application_hour: int = Field(0, ge=0, le=23)


class OnboardingBatchRequest(BaseModel):
    """Batch of onboarding assessment requests."""
    applications: List[OnboardingAssessRequest] = Field(
        ..., min_length=1, max_length=100
    )
