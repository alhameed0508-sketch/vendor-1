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
    device_fingerprint: Optional[str] = None
    ip_address: Optional[str] = None
    phone_number: Optional[str] = None
    full_name: Optional[str] = Field(None, max_length=200)
    email_address: Optional[str] = Field(None, max_length=254)
    postal_address: Optional[str] = Field(None, max_length=500)
    government_id_hash: Optional[str] = Field(
        None,
        min_length=32,
        max_length=128,
    )


class EntityResolveRequest(BaseModel):
    """Identity attributes used to find linked or duplicate profiles."""

    account_id: str = Field(..., min_length=1, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=200)
    phone_number: Optional[str] = Field(None, max_length=30)
    email_address: Optional[str] = Field(None, max_length=254)
    postal_address: Optional[str] = Field(None, max_length=500)
    government_id_hash: Optional[str] = Field(
        None,
        min_length=32,
        max_length=128,
    )
    device_fingerprint: Optional[str] = Field(None, max_length=128)


class OnboardingBatchRequest(BaseModel):
    """Batch of onboarding assessment requests."""

    applications: List[OnboardingAssessRequest] = Field(
        ..., min_length=1, max_length=100
    )
