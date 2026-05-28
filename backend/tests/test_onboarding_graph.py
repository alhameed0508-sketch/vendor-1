"""Tests for graph cross-check at onboarding (OB15)."""
import pytest
from models.onboarding.risk_scorer import (
    assess_onboarding_risk,
    _score_graph_cross_check,
    SIGNAL_WEIGHTS,
    REASON_CODES,
)


class TestGraphCrossCheckScorer:
    def test_no_flagged(self):
        assert _score_graph_cross_check(0) == 0.0

    def test_one_flagged(self):
        score = _score_graph_cross_check(1)
        assert 0.0 < score < 1.0

    def test_many_flagged(self):
        assert _score_graph_cross_check(5) == 1.0

    def test_cluster_boost(self):
        score_no_cluster = _score_graph_cross_check(2, cluster_count=0)
        score_with_clusters = _score_graph_cross_check(2, cluster_count=3)
        assert score_with_clusters > score_no_cluster


class TestSignalWeightsIntegrity:
    def test_weights_sum_to_one(self):
        total = sum(SIGNAL_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_graph_cross_check_weight_exists(self):
        assert "graph_cross_check" in SIGNAL_WEIGHTS

    def test_ob15_reason_code_exists(self):
        assert "graph_cross_check" in REASON_CODES
        code, desc = REASON_CODES["graph_cross_check"]
        assert code == "OB15"


class TestGraphCheckerIntegration:
    def test_with_graph_checker(self):
        def mock_checker(device_id=None, ip_address=None, phone=None):
            return {"flagged_count": 3, "flagged_accounts": ["M1", "M2", "M3"], "cluster_ids": ["C1"]}

        app = {"account_id": "TEST_001", "device_fingerprint": "DEV_123"}
        result = assess_onboarding_risk(app, graph_checker=mock_checker)
        assert result.risk_score > 0
        assert any("OB15" in rc for rc in result.reason_codes)

    def test_without_graph_checker(self):
        app = {"account_id": "TEST_002"}
        result = assess_onboarding_risk(app, graph_checker=None)
        # Should still work, just no graph signal
        assert result.risk_score >= 0

    def test_graph_checker_failure_graceful(self):
        def failing_checker(**kwargs):
            raise ConnectionError("Neo4j unavailable")

        app = {"account_id": "TEST_003", "device_fingerprint": "DEV_X"}
        result = assess_onboarding_risk(app, graph_checker=failing_checker)
        # Should fall back gracefully
        assert result.risk_score >= 0

    def test_with_application_data_fallback(self):
        app = {
            "account_id": "TEST_004",
            "graph_flagged_count": 4,
            "graph_cluster_count": 2,
        }
        result = assess_onboarding_risk(app)
        assert any("OB15" in rc for rc in result.reason_codes)
