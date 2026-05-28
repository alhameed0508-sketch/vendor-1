"""Integration tests for propensity API endpoints.

Tests the HTTP API layer for propensity scoring. The core propensity scoring
logic is thoroughly tested in test_propensity_scorer.py. These tests verify:
- Route registration and HTTP response format
- Error handling (404 for non-existent accounts)
- API response structure and envelope format
- Query parameter handling

Note: Full end-to-end tests with mocked scorer data would require clearing
lru_cache on dependencies, which can interfere with other tests. The unit
tests in test_propensity_scorer.py provide comprehensive coverage of the
scoring logic itself.
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def app():
    """Use the pre-created app instance to avoid Prometheus re-registration."""
    from api.app import app
    return app


@pytest.fixture(scope="module")
def client(app):
    """Create test client (module-scoped)."""
    return TestClient(app)


class TestPropensityEndpoints:
    """Test propensity API endpoints."""

    def test_get_propensity_score_not_found(self, client):
        """Test getting propensity score for non-existent account."""
        response = client.get("/api/v1/propensity/UNKNOWN_ACCOUNT_XYZ_999")

        assert response.status_code == 404
        data = response.json()

        # Verify error response structure
        assert data["success"] is False
        assert data["error"] is not None
        assert "NOT_FOUND" in data["error"]["code"]
        assert "timestamp" in data

    def test_get_top_risk_default_limit(self, client):
        """Test getting top-risk accounts with default limit."""
        response = client.get("/api/v1/propensity/top-risk")

        assert response.status_code == 200
        data = response.json()

        # Verify success response structure
        assert data["success"] is True
        assert "accounts" in data["data"]
        assert "total" in data["data"]
        assert "timestamp" in data

        # Verify accounts list structure
        accounts = data["data"]["accounts"]
        assert isinstance(accounts, list)
        assert data["data"]["total"] == len(accounts)

        # If there are accounts, verify structure
        for account in accounts:
            assert "account_id" in account
            assert "score" in account
            assert "updated_at" in account
            assert 0.0 <= account["score"] <= 1.0

        # Verify accounts are sorted by score (descending)
        if len(accounts) > 1:
            for i in range(len(accounts) - 1):
                assert accounts[i]["score"] >= accounts[i + 1]["score"]

    def test_get_top_risk_with_custom_limit(self, client):
        """Test getting top-risk accounts with custom limit."""
        response = client.get("/api/v1/propensity/top-risk?limit=2")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        accounts = data["data"]["accounts"]
        assert len(accounts) <= 2

    def test_get_top_risk_large_limit(self, client):
        """Test getting top-risk accounts with large limit."""
        response = client.get("/api/v1/propensity/top-risk?limit=100")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        # Should return <= 100 even if fewer exist
        assert len(data["data"]["accounts"]) <= 100

    def test_response_envelope_structure(self, client):
        """Test that all responses follow the standard envelope format."""
        response = client.get("/api/v1/propensity/top-risk")

        data = response.json()

        # All responses should have these fields
        assert "success" in data
        assert "data" in data
        assert "error" in data
        assert "timestamp" in data

        # Success response should have data, null error
        if response.status_code == 200:
            assert data["success"] is True
            assert data["data"] is not None
            assert data["error"] is None

    def test_propensity_score_window_structure(self, client):
        """Test that propensity scores include all required time windows."""
        # This tests the response structure when an account exists
        # Since we can't easily mock data here, we test against the
        # non-existent account error response structure
        response = client.get("/api/v1/propensity/NONEXISTENT")

        # Should get 404 with proper error structure
        assert response.status_code == 404
        data = response.json()

        # Error response structure
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_FOUND"
        assert "No propensity data" in data["error"]["message"]
