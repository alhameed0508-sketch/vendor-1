"""Integration coverage for onboarding and watchlist screening APIs."""

import os
import sys

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from api.app import app
from api.deps import get_screening_repository


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as api_client:
        yield api_client


def _data(response):
    body = response.json()
    assert body["success"] is True, body
    return body["data"]


@pytest.mark.asyncio
async def test_onboarding_assessment_lifecycle(client):
    payload = {
        "account_id": "ONB-API-001",
        "kyc_completeness": 0.45,
        "doc_verification_seconds": 8,
        "device_overlap_count": 4,
        "ip_geolocation_mismatch": True,
        "phone_age_days": 3,
        "email_age_days": 2,
        "address_verified": False,
        "selfie_confidence": 0.55,
        "application_velocity_count": 6,
        "similar_name_count": 3,
        "high_risk_geography": True,
        "application_hour": 2,
    }
    response = await client.post("/api/v1/onboarding/assess", json=payload)
    assert response.status_code == 200
    assessment = _data(response)
    assert assessment["account_id"] == payload["account_id"]
    assert 0 <= assessment["risk_score"] <= 1
    assert assessment["reason_codes"]

    response = await client.get(
        f"/api/v1/onboarding/assessments/{assessment['assessment_id']}"
    )
    assert response.status_code == 200
    assert _data(response)["assessment_id"] == assessment["assessment_id"]

    response = await client.get("/api/v1/onboarding/stats")
    assert response.status_code == 200
    assert _data(response)["total_assessed"] >= 1


@pytest.mark.asyncio
async def test_onboarding_unknown_assessment_is_404(client):
    response = await client.get("/api/v1/onboarding/assessments/OBA-DOES-NOT-EXIST")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_entity_resolution_links_name_variant_with_same_phone(client):
    first = {
        "account_id": "ENTITY-001",
        "full_name": "Anita Ramesh Kumar",
        "phone_number": "+91 98765 43210",
        "email_address": "anita@example.test",
        "postal_address": "12 Mount Road Chennai",
    }
    second = {
        "account_id": "ENTITY-002",
        "full_name": "Anitha R Kumar",
        "phone_number": "+91-98765-43210",
        "email_address": "other@example.test",
        "postal_address": "12 Mount Rd, Chennai",
    }
    first_response = await client.post(
        "/api/v1/onboarding/resolve-identity",
        json=first,
    )
    assert first_response.status_code == 200
    assert _data(first_response)["match_count"] == 0

    second_response = await client.post(
        "/api/v1/onboarding/resolve-identity",
        json=second,
    )
    assert second_response.status_code == 200
    resolution = _data(second_response)
    assert resolution["decision"] == "REVIEW_LINKED_IDENTITIES"
    assert resolution["matches"][0]["entity_id"] == "ENTITY-001"
    assert "phone_hash" in resolution["matches"][0]["matched_fields"]


@pytest.mark.asyncio
async def test_device_event_ingestion_returns_trust_signal(client):
    response = await client.post(
        "/api/v1/device/events",
        json={
            "account_id": "DEVICE-API-001",
            "device_fingerprint_hash": "a" * 32,
            "source_channel": "WEB",
            "is_bot": True,
        },
    )
    assert response.status_code == 200
    result = _data(response)
    assert result["accepted"] is True
    assert result["device_trust_score"] > 0
    assert any("DP05" in code for code in result["reason_codes"])


@pytest.mark.asyncio
async def test_screening_exact_name_and_identifier_match(client):
    repository = get_screening_repository()
    repository.bulk_import_entries(
        [
            {
                "entry_id": "TEST-SANCTION-001",
                "name": "Example Sanctioned Person",
                "aliases": ["Example Alias"],
                "identifiers": ["P1234567"],
                "entity_type": "INDIVIDUAL",
                "countries": ["XZ"],
                "risk_category": "SANCTIONS",
            }
        ],
        source="TEST",
    )

    response = await client.post(
        "/api/v1/screening/screen",
        json={
            "account_id": "SCR-API-001",
            "name": "Example Sanctioned Person",
            "identifiers": ["P1234567"],
        },
    )
    assert response.status_code == 200
    result = _data(response)
    assert result["status"] == "MATCH"
    assert result["highest_confidence"] == 1.0

    response = await client.get("/api/v1/screening/results/SCR-API-001")
    assert response.status_code == 200
    assert len(_data(response)) == 1

    response = await client.get("/api/v1/screening/stats")
    assert response.status_code == 200
    assert _data(response)["total_entries"] >= 1


@pytest.mark.asyncio
async def test_batch_limits_are_validated(client):
    response = await client.post(
        "/api/v1/onboarding/assess-batch", json={"applications": []}
    )
    assert response.status_code == 422

    response = await client.post(
        "/api/v1/screening/screen-batch", json={"accounts": []}
    )
    assert response.status_code == 422
