"""
Tests for onboarding risk assessment — service, repository, API endpoints.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from repositories.onboarding_repository import OnboardingRepository
from services.onboarding_service import OnboardingService


@pytest.fixture
def repo():
    return OnboardingRepository()


@pytest.fixture
def service(repo):
    return OnboardingService(repo)


@pytest.fixture
def high_risk_application():
    """Application that should trigger high risk score."""
    return {
        "account_id": "AC_HR_001",
        "account_age_days": 2,
        "kyc_completeness": 0.3,
        "doc_verification_seconds": 8,
        "device_overlap_count": 3,
        "ip_geolocation_mismatch": True,
        "phone_age_days": 5,
        "email_age_days": 2,
        "address_verified": False,
        "selfie_confidence": 0.5,
        "application_velocity_count": 4,
        "similar_name_count": 2,
        "high_risk_geography": True,
        "application_hour": 3,
    }


@pytest.fixture
def low_risk_application():
    """Application that should produce low risk score."""
    return {
        "account_id": "AC_LR_001",
        "account_age_days": 365,
        "kyc_completeness": 0.95,
        "doc_verification_seconds": 120,
        "device_overlap_count": 0,
        "ip_geolocation_mismatch": False,
        "phone_age_days": 730,
        "email_age_days": 1825,
        "address_verified": True,
        "selfie_confidence": 0.98,
        "application_velocity_count": 0,
        "similar_name_count": 0,
        "high_risk_geography": False,
        "application_hour": 14,
    }


# ── Repository tests ─────────────────────────────────────────────────────────


class TestOnboardingRepository:
    def test_store_and_retrieve(self, repo):
        assessment = {
            "assessment_id": "OB_001",
            "account_id": "AC_001",
            "risk_score": 0.65,
            "risk_level": "HIGH",
        }
        repo.store_assessment(assessment)
        result = repo.get_assessment("OB_001")
        assert result is not None
        assert result["risk_score"] == 0.65

    def test_get_nonexistent(self, repo):
        assert repo.get_assessment("NONEXISTENT") is None

    def test_list_assessments(self, repo):
        for i in range(5):
            repo.store_assessment({
                "assessment_id": f"OB_{i}",
                "account_id": f"AC_{i}",
                "risk_level": "HIGH" if i % 2 == 0 else "LOW",
            })
        results = repo.get_assessments(limit=3)
        assert len(results) == 3

    def test_filter_by_risk_level(self, repo):
        repo.store_assessment({"assessment_id": "A1", "risk_level": "HIGH"})
        repo.store_assessment({"assessment_id": "A2", "risk_level": "LOW"})
        repo.store_assessment({"assessment_id": "A3", "risk_level": "HIGH"})

        high = repo.get_assessments(risk_level="HIGH")
        assert len(high) == 2
        assert all(a["risk_level"] == "HIGH" for a in high)

    def test_stats(self, repo):
        repo.store_assessment({
            "assessment_id": "S1", "risk_level": "HIGH",
            "recommendation": "BLOCK",
        })
        repo.store_assessment({
            "assessment_id": "S2", "risk_level": "LOW",
            "recommendation": "APPROVE",
        })
        stats = repo.get_stats()
        assert stats["total_assessed"] == 2
        assert stats["high_risk_flagged"] == 1


# ── Service tests ─────────────────────────────────────────────────────────────


class TestOnboardingService:
    def test_assess_high_risk(self, service, high_risk_application):
        result = service.assess_account(high_risk_application)
        assert "assessment_id" in result
        assert "risk_score" in result
        assert "risk_level" in result
        assert result["risk_score"] > 0.3

    def test_assess_low_risk(self, service, low_risk_application):
        result = service.assess_account(low_risk_application)
        assert result["risk_level"] in ("LOW", "MEDIUM")

    def test_assess_returns_reason_codes(self, service, high_risk_application):
        result = service.assess_account(high_risk_application)
        assert "reason_codes" in result
        assert isinstance(result["reason_codes"], list)

    def test_assess_returns_signals(self, service, high_risk_application):
        result = service.assess_account(high_risk_application)
        assert "signals" in result
        assert len(result["signals"]) > 0
        for sig in result["signals"]:
            assert "signal" in sig
            assert "score" in sig

    def test_batch_assess(self, service, high_risk_application, low_risk_application):
        results = service.assess_batch([high_risk_application, low_risk_application])
        assert len(results) == 2

    def test_get_assessment_persisted(self, service, high_risk_application):
        result = service.assess_account(high_risk_application)
        assessment_id = result["assessment_id"]
        retrieved = service.get_assessment(assessment_id)
        assert retrieved is not None
        assert retrieved["assessment_id"] == assessment_id

    def test_list_assessments(self, service, high_risk_application, low_risk_application):
        service.assess_account(high_risk_application)
        service.assess_account(low_risk_application)
        assessments = service.get_assessments(limit=10)
        assert len(assessments) >= 2

    def test_stats_updated(self, service, high_risk_application):
        service.assess_account(high_risk_application)
        stats = service.get_stats()
        assert stats["total_assessed"] >= 1

    def test_recommendation_present(self, service, high_risk_application):
        result = service.assess_account(high_risk_application)
        assert "recommendation" in result
        assert len(result["recommendation"]) > 0
