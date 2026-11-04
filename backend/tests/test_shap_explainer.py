"""
Tests for the SHAP Alert Explainer module.

Verifies:
  - Global importance correctly ranks features
  - Per-alert explanation produces valid Shapley values
  - Top positive/negative features are correctly identified
  - Regulatory report contains all required fields
  - Fallback works when shap is not installed
  - Edge cases: single feature alert, all features zero, missing data
  - Explanation text is human-readable and non-empty

Run: python -m pytest backend/tests/test_shap_explainer.py -v
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import numpy as np
import pytest

from models.explainability.shap_explainer import (
    FEATURE_DESCRIPTIONS,
    FEATURE_NAMES,
    AlertExplanation,
    GlobalImportance,
    SHAPAlertExplainer,
    _extract_batch_features,
    _extract_features,
    _surrogate_score,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_alert() -> dict:
    """A realistic alert dict matching the pipeline's output structure."""
    return {
        "alert_id": "ALT_TEST_001",
        "risk_score": 0.82,
        "severity": "CRITICAL",
        "account_count": 5,
        "total_amount": 450000.0,
        "txn_count": 23,
        "nodes": [
            {
                "account_id": "ACC_001",
                "role": "SOURCE",
                "smurf_score": 0.85,
                "baseline_deviation": 0.7,
                "device_trust_score": 0.6,
                "semantics_score": 0.4,
                "betweenness": 0.3,
                "pagerank": 0.05,
                "account_age_days": 5,
                "kyc_status": "PENDING",
                "bank": "IOBA",
                "city": "Mumbai",
                "upi_id": "acc001@upi",
            },
            {
                "account_id": "ACC_002",
                "role": "MULE",
                "smurf_score": 0.65,
                "baseline_deviation": 0.5,
                "device_trust_score": 0.8,
                "semantics_score": 0.3,
                "betweenness": 0.1,
                "pagerank": 0.03,
                "account_age_days": 10,
                "kyc_status": "VERIFIED",
                "bank": "IOBA",
                "city": "Delhi",
                "upi_id": "acc002@upi",
            },
            {
                "account_id": "ACC_003",
                "role": "AGGREGATOR",
                "smurf_score": 0.55,
                "baseline_deviation": 0.3,
                "device_trust_score": 0.2,
                "semantics_score": 0.6,
                "betweenness": 0.5,
                "pagerank": 0.08,
                "account_age_days": 200,
                "kyc_status": "VERIFIED",
                "bank": "SBI",
                "city": "Chennai",
                "upi_id": "acc003@upi",
            },
        ],
        "edges": [
            {
                "from_account": "ACC_001",
                "to_account": "ACC_002",
                "total_amount": 200000,
                "txn_count": 10,
                "pattern": "RAPID_BURST",
                "timestamps": ["2024-01-01T10:00:00"],
            },
            {
                "from_account": "ACC_002",
                "to_account": "ACC_003",
                "total_amount": 250000,
                "txn_count": 13,
                "pattern": "STRUCTURING",
                "timestamps": ["2024-01-01T11:00:00"],
            },
        ],
        "reason_codes": [
            "R01: Account age < 7 days",
            "R02: > 20 transactions in 24h",
            "R06: Same-day credit-debit",
            "RC01: High velocity score",
            "RC02: Amount structuring detected",
        ],
        "shared_devices": ["DEV_A"],
        "shared_ips": ["192.168.1.1"],
        "gnn_score": 0.78,
    }


@pytest.fixture
def sample_alerts(sample_alert) -> list:
    """A batch of alerts for global importance testing."""
    alert2 = {
        "alert_id": "ALT_TEST_002",
        "risk_score": 0.55,
        "severity": "MEDIUM",
        "account_count": 3,
        "nodes": [
            {
                "account_id": "ACC_010",
                "role": "MULE",
                "smurf_score": 0.40,
                "baseline_deviation": 0.2,
                "device_trust_score": 0.1,
                "semantics_score": 0.15,
                "betweenness": 0.05,
                "pagerank": 0.01,
                "account_age_days": 300,
                "kyc_status": "VERIFIED",
                "bank": "HDFC",
                "city": "Pune",
                "upi_id": "acc010@upi",
            },
        ],
        "edges": [],
        "reason_codes": ["R06: Same-day credit-debit"],
        "shared_devices": [],
        "shared_ips": [],
        "gnn_score": None,
    }
    return [sample_alert, alert2]


@pytest.fixture
def explainer() -> SHAPAlertExplainer:
    """A default explainer instance."""
    return SHAPAlertExplainer()


@pytest.fixture
def zero_alert() -> dict:
    """An alert where all features are zero."""
    return {
        "alert_id": "ALT_ZERO",
        "risk_score": 0.0,
        "severity": "MEDIUM",
        "nodes": [
            {
                "account_id": "ACC_ZERO",
                "role": "UNKNOWN",
                "smurf_score": 0.0,
                "baseline_deviation": 0.0,
                "device_trust_score": 0.0,
                "semantics_score": 0.0,
                "betweenness": 0.0,
                "pagerank": 0.0,
                "account_age_days": 0,
                "kyc_status": "UNKNOWN",
                "bank": "",
                "city": "",
                "upi_id": "",
            },
        ],
        "edges": [],
        "reason_codes": [],
        "shared_devices": [],
        "shared_ips": [],
    }


@pytest.fixture
def single_feature_alert() -> dict:
    """An alert where only one feature is non-zero."""
    return {
        "alert_id": "ALT_SINGLE",
        "risk_score": 0.3,
        "severity": "MEDIUM",
        "nodes": [
            {
                "account_id": "ACC_SINGLE",
                "role": "MULE",
                "smurf_score": 0.9,
                "baseline_deviation": 0.0,
                "device_trust_score": 0.0,
                "semantics_score": 0.0,
                "betweenness": 0.0,
                "pagerank": 0.0,
                "account_age_days": 0,
                "kyc_status": "UNKNOWN",
                "bank": "",
                "city": "",
                "upi_id": "",
            },
        ],
        "edges": [],
        "reason_codes": [],
        "shared_devices": [],
        "shared_ips": [],
    }


# ---------------------------------------------------------------------------
# Feature extraction tests
# ---------------------------------------------------------------------------


class TestFeatureExtraction:
    def test_extract_features_shape(self, sample_alert):
        features = _extract_features(sample_alert)
        assert features.shape == (len(FEATURE_NAMES),)

    def test_extract_features_values_in_range(self, sample_alert):
        features = _extract_features(sample_alert)
        # All features should be finite
        assert np.all(np.isfinite(features))

    def test_extract_batch_features_shape(self, sample_alerts):
        features = _extract_batch_features(sample_alerts)
        assert features.shape == (2, len(FEATURE_NAMES))

    def test_extract_features_empty_nodes(self):
        features = _extract_features({"nodes": [], "reason_codes": []})
        assert features.shape == (len(FEATURE_NAMES),)
        # All should be zero
        assert np.allclose(features, 0.0)

    def test_extract_features_max_aggregation(self, sample_alert):
        """Max aggregation should pick highest smurf_score from nodes."""
        features = _extract_features(sample_alert)
        smurf_idx = list(FEATURE_NAMES).index("smurf_score")
        assert features[smurf_idx] == 0.85  # max of 0.85, 0.65, 0.55

    def test_extract_features_rule_hit_count(self, sample_alert):
        features = _extract_features(sample_alert)
        rule_idx = list(FEATURE_NAMES).index("rule_hit_count")
        # 3 rule codes starting with R0x: R01, R02, R06
        assert features[rule_idx] == pytest.approx(3.0 / 10.0)

    def test_extract_features_missing_data(self):
        """Alert with missing fields should not crash."""
        features = _extract_features({"nodes": [{"account_id": "X"}]})
        assert features.shape == (len(FEATURE_NAMES),)
        assert np.all(np.isfinite(features))


# ---------------------------------------------------------------------------
# Surrogate scoring tests
# ---------------------------------------------------------------------------


class TestSurrogateScore:
    def test_output_shape(self):
        features = np.random.rand(5, len(FEATURE_NAMES))
        scores = _surrogate_score(features)
        assert scores.shape == (5,)

    def test_output_range(self):
        features = np.random.rand(10, len(FEATURE_NAMES))
        scores = _surrogate_score(features)
        assert np.all(scores >= 0) and np.all(scores <= 1)

    def test_single_input(self):
        features = np.random.rand(len(FEATURE_NAMES))
        scores = _surrogate_score(features)
        assert scores.shape == (1,)

    def test_zero_features(self):
        features = np.zeros((1, len(FEATURE_NAMES)))
        scores = _surrogate_score(features)
        assert scores.shape == (1,)
        assert 0 < scores[0] < 1


# ---------------------------------------------------------------------------
# Global importance tests
# ---------------------------------------------------------------------------


class TestGlobalImportance:
    def test_returns_global_importance(self, explainer, sample_alerts):
        result = explainer.compute_global_importance(sample_alerts)
        assert isinstance(result, GlobalImportance)

    def test_rankings_contain_all_features(self, explainer, sample_alerts):
        result = explainer.compute_global_importance(sample_alerts)
        ranked_names = {name for name, _ in result.feature_rankings}
        assert ranked_names == set(FEATURE_NAMES)

    def test_rankings_sorted_descending(self, explainer, sample_alerts):
        result = explainer.compute_global_importance(sample_alerts)
        scores = [s for _, s in result.feature_rankings]
        assert scores == sorted(scores, reverse=True)

    def test_top_features_populated(self, explainer, sample_alerts):
        result = explainer.compute_global_importance(sample_alerts)
        assert len(result.top_features) == 3
        for name in result.top_features:
            assert name in FEATURE_NAMES

    def test_importances_non_negative(self, explainer, sample_alerts):
        result = explainer.compute_global_importance(sample_alerts)
        for _, score in result.feature_rankings:
            assert score >= 0

    def test_smurf_score_ranks_high(self, explainer, sample_alerts):
        """smurf_score has weight 0.30 — should rank highly."""
        result = explainer.compute_global_importance(sample_alerts)
        top_5_names = [n for n, _ in result.feature_rankings[:5]]
        assert "smurf_score" in top_5_names

    def test_empty_alerts_returns_zero_rankings(self, explainer):
        result = explainer.compute_global_importance([])
        assert isinstance(result, GlobalImportance)
        for _, score in result.feature_rankings:
            assert score == 0.0

    def test_to_dict_serializable(self, explainer, sample_alerts):
        result = explainer.compute_global_importance(sample_alerts)
        d = result.to_dict()
        json.dumps(d)  # must not raise

    def test_method_field(self, explainer, sample_alerts):
        result = explainer.compute_global_importance(sample_alerts)
        assert result.method in ("shap", "permutation")


# ---------------------------------------------------------------------------
# Per-alert explanation tests
# ---------------------------------------------------------------------------


class TestAlertExplanation:
    def test_returns_alert_explanation(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        assert isinstance(result, AlertExplanation)

    def test_alert_id_matches(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        assert result.alert_id == "ALT_TEST_001"

    def test_base_score_is_float(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        assert isinstance(result.base_score, float)
        assert 0.0 <= result.base_score <= 1.0

    def test_all_features_have_contributions(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        assert set(result.feature_contributions.keys()) == set(FEATURE_NAMES)

    def test_shapley_values_sum_approximately_equals_prediction_minus_base(
        self,
        explainer,
        sample_alert,
    ):
        """
        Fundamental SHAP property: sum of Shapley values should
        approximately equal (prediction - base_score).
        """
        result = explainer.explain_alert(sample_alert)
        features = _extract_features(sample_alert)
        prediction = float(_surrogate_score(features.reshape(1, -1)).flat[0])
        total_contributions = sum(result.feature_contributions.values())
        expected_diff = prediction - result.base_score
        # Allow tolerance for approximation
        assert abs(total_contributions - expected_diff) < 0.15, (
            f"Sum of Shapley values ({total_contributions:.4f}) should "
            f"approximately equal prediction - base "
            f"({prediction:.4f} - {result.base_score:.4f} = {expected_diff:.4f})"
        )

    def test_top_positive_features_are_positive(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        for name, value in result.top_positive_features:
            assert value > 0, f"Positive feature {name} has value {value}"
            assert name in FEATURE_NAMES

    def test_top_negative_features_are_negative(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        for name, value in result.top_negative_features:
            assert value < 0, f"Negative feature {name} has value {value}"
            assert name in FEATURE_NAMES

    def test_high_smurf_contributes_positively(self, explainer, sample_alert):
        """Alert with smurf_score=0.85 should have positive smurf contribution."""
        result = explainer.explain_alert(sample_alert)
        assert result.feature_contributions["smurf_score"] > 0

    def test_to_dict_serializable(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        d = result.to_dict()
        json.dumps(d)  # must not raise

    def test_method_field(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        assert result.method in ("kernel_shap", "permutation")


# ---------------------------------------------------------------------------
# Explanation text tests
# ---------------------------------------------------------------------------


class TestExplanationText:
    def test_text_is_non_empty(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        assert len(result.explanation_text) > 0

    def test_text_is_human_readable(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        text = result.explanation_text
        # Should contain the alert ID
        assert "ALT_TEST_001" in text
        # Should contain a percentage
        assert "%" in text
        # Should be a proper sentence
        assert text.endswith(".")

    def test_text_mentions_risk_drivers(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        # Should mention at least one feature description
        has_feature_desc = any(
            desc.lower() in result.explanation_text.lower() for desc in FEATURE_DESCRIPTIONS.values()
        )
        assert has_feature_desc, "Explanation should mention feature descriptions"

    def test_high_risk_alert_text_has_urgency(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        text = result.explanation_text.lower()
        # High-risk alert should have urgent language
        assert any(word in text for word in ["immediate", "priority", "high-confidence"])


# ---------------------------------------------------------------------------
# Regulatory report tests
# ---------------------------------------------------------------------------


class TestRegulatoryReport:
    def test_contains_required_fields(self, explainer, sample_alert):
        explanation = explainer.explain_alert(sample_alert)
        report = explainer.generate_regulatory_report(explanation)
        required_fields = [
            "alert_id",
            "model_type",
            "feature_list",
            "top_contributing_features",
            "explainability_method",
            "confidence_score",
            "audit_trail",
        ]
        for field_name in required_fields:
            assert field_name in report, f"Missing required field: {field_name}"

    def test_explainability_method_value(self, explainer, sample_alert):
        explanation = explainer.explain_alert(sample_alert)
        report = explainer.generate_regulatory_report(explanation)
        assert report["explainability_method"] == "Kernel SHAP approximation"

    def test_feature_list_complete(self, explainer, sample_alert):
        explanation = explainer.explain_alert(sample_alert)
        report = explainer.generate_regulatory_report(explanation)
        assert set(report["feature_list"]) == set(FEATURE_NAMES)

    def test_top_contributing_features_structure(self, explainer, sample_alert):
        explanation = explainer.explain_alert(sample_alert)
        report = explainer.generate_regulatory_report(explanation)
        top_features = report["top_contributing_features"]
        assert len(top_features) > 0
        for feat in top_features:
            assert "feature" in feat
            assert "description" in feat
            assert "shapley_value" in feat
            assert "direction" in feat
            assert feat["direction"] in ("increases risk", "decreases risk")

    def test_confidence_score_range(self, explainer, sample_alert):
        explanation = explainer.explain_alert(sample_alert)
        report = explainer.generate_regulatory_report(explanation)
        assert 0.0 <= report["confidence_score"] <= 1.0

    def test_audit_trail_structure(self, explainer, sample_alert):
        explanation = explainer.explain_alert(sample_alert)
        report = explainer.generate_regulatory_report(explanation)
        audit = report["audit_trail"]
        assert "method_used" in audit
        assert "feature_count" in audit
        assert "features_analyzed" in audit
        assert "positive_contributors" in audit
        assert "negative_contributors" in audit
        assert "framework_compliance" in audit
        assert "explanation_text" in audit
        assert audit["framework_compliance"] == "RBI FREE-AI (August 2025)"

    def test_report_serializable(self, explainer, sample_alert):
        explanation = explainer.explain_alert(sample_alert)
        report = explainer.generate_regulatory_report(explanation)
        json.dumps(report)  # must not raise

    def test_alert_id_propagated(self, explainer, sample_alert):
        explanation = explainer.explain_alert(sample_alert)
        report = explainer.generate_regulatory_report(explanation)
        assert report["alert_id"] == "ALT_TEST_001"

    def test_base_score_in_report(self, explainer, sample_alert):
        explanation = explainer.explain_alert(sample_alert)
        report = explainer.generate_regulatory_report(explanation)
        assert "base_score" in report
        assert isinstance(report["base_score"], float)


# ---------------------------------------------------------------------------
# Fallback / permutation-based tests
# ---------------------------------------------------------------------------


class TestFallback:
    def test_permutation_fallback_works(self, sample_alert):
        """Verify that the permutation fallback produces valid results."""
        explainer = SHAPAlertExplainer()
        # Force permutation mode by calling internal method directly
        features = _extract_features(sample_alert)
        contributions, base_score = explainer._permutation_explain(features)
        assert contributions.shape == (len(FEATURE_NAMES),)
        assert isinstance(base_score, float)
        assert 0.0 <= base_score <= 1.0

    def test_permutation_contributions_finite(self, sample_alert):
        explainer = SHAPAlertExplainer()
        features = _extract_features(sample_alert)
        contributions, _ = explainer._permutation_explain(features)
        assert np.all(np.isfinite(contributions))

    def test_permutation_explain_full_pipeline(self, sample_alert):
        """Simulate shap not installed by using permutation path directly."""
        import models.explainability.shap_explainer as module

        original = module._shap_available
        try:
            module._shap_available = False
            explainer = SHAPAlertExplainer()
            explainer._use_shap = False
            result = explainer.explain_alert(sample_alert)
            assert result.method == "permutation"
            assert len(result.feature_contributions) == len(FEATURE_NAMES)
        finally:
            module._shap_available = original

    def test_fallback_global_importance(self, sample_alerts):
        """Global importance works in fallback mode."""
        import models.explainability.shap_explainer as module

        original = module._shap_available
        try:
            module._shap_available = False
            explainer = SHAPAlertExplainer()
            explainer._use_shap = False
            result = explainer.compute_global_importance(sample_alerts)
            assert result.method == "permutation"
            assert len(result.feature_rankings) == len(FEATURE_NAMES)
        finally:
            module._shap_available = original


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_all_features_zero(self, explainer, zero_alert):
        result = explainer.explain_alert(zero_alert)
        assert result.alert_id == "ALT_ZERO"
        assert isinstance(result.base_score, float)
        # With all features zero, contributions should all be ~0
        total = sum(abs(v) for v in result.feature_contributions.values())
        assert total < 0.1, "All-zero features should yield near-zero contributions"

    def test_single_nonzero_feature(self, explainer, single_feature_alert):
        result = explainer.explain_alert(single_feature_alert)
        assert result.alert_id == "ALT_SINGLE"
        # smurf_score should be the dominant contributor
        smurf_contrib = result.feature_contributions["smurf_score"]
        other_max = max(abs(v) for k, v in result.feature_contributions.items() if k != "smurf_score")
        assert abs(smurf_contrib) >= other_max, "With only smurf_score non-zero, it should be the dominant contributor"

    def test_missing_nodes(self, explainer):
        result = explainer.explain_alert({"alert_id": "EMPTY", "reason_codes": []})
        assert result.alert_id == "EMPTY"
        assert len(result.feature_contributions) == len(FEATURE_NAMES)

    def test_missing_reason_codes(self, explainer):
        alert = {
            "alert_id": "NO_CODES",
            "nodes": [
                {
                    "account_id": "X",
                    "smurf_score": 0.5,
                    "baseline_deviation": 0.3,
                    "device_trust_score": 0.0,
                    "semantics_score": 0.0,
                    "betweenness": 0.0,
                    "pagerank": 0.0,
                    "account_age_days": 100,
                },
            ],
        }
        result = explainer.explain_alert(alert)
        assert result.feature_contributions["rule_hit_count"] == pytest.approx(0.0, abs=0.01)

    def test_large_batch_global_importance(self, explainer):
        """Test with a larger batch to ensure no performance/correctness issues."""
        alerts = []
        for i in range(20):
            alerts.append(
                {
                    "alert_id": f"ALT_BATCH_{i}",
                    "nodes": [
                        {
                            "account_id": f"ACC_{i}",
                            "smurf_score": np.random.rand(),
                            "baseline_deviation": np.random.rand(),
                            "device_trust_score": np.random.rand(),
                            "semantics_score": np.random.rand(),
                            "betweenness": np.random.rand() * 0.5,
                            "pagerank": np.random.rand() * 0.1,
                            "account_age_days": int(np.random.rand() * 730),
                            "kyc_status": "VERIFIED",
                        },
                    ],
                    "reason_codes": [f"R0{j}: Rule {j}" for j in range(1, 4)],
                }
            )
        result = explainer.compute_global_importance(alerts)
        assert len(result.feature_rankings) == len(FEATURE_NAMES)
        assert len(result.top_features) == 3

    def test_custom_score_function(self, sample_alert):
        """SHAPAlertExplainer should work with a custom scoring function."""

        def custom_fn(features):
            if features.ndim == 1:
                features = features.reshape(1, -1)
            return features[:, 0] * 0.5 + 0.25

        explainer = SHAPAlertExplainer(score_fn=custom_fn)
        result = explainer.explain_alert(sample_alert)
        assert isinstance(result, AlertExplanation)
        assert len(result.feature_contributions) == len(FEATURE_NAMES)
        # smurf_score (index 0) should dominate since custom_fn only uses it
        assert abs(result.feature_contributions["smurf_score"]) > 0


# ---------------------------------------------------------------------------
# Immutability tests
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_alert_explanation_is_frozen(self, explainer, sample_alert):
        result = explainer.explain_alert(sample_alert)
        with pytest.raises(AttributeError):
            result.alert_id = "MODIFIED"

    def test_global_importance_is_frozen(self, explainer, sample_alerts):
        result = explainer.compute_global_importance(sample_alerts)
        with pytest.raises(AttributeError):
            result.method = "MODIFIED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
