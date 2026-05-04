"""
Tests for SHAP explainer, narrative generator, and mule classifier.
Run: python -m pytest backend/tests/test_explainability.py -v
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
from data.synthetic.generator import build_full_dataset
from backend.detection.pipeline import DetectionPipeline


@pytest.fixture(scope="module")
def pipeline_results():
    dataset = build_full_dataset(num_clusters=2, num_legit_accounts=15)
    pipeline = DetectionPipeline()
    alerts = pipeline.run(dataset["transactions"], dataset["accounts"])
    return {"alerts": alerts, "dataset": dataset}


@pytest.fixture(scope="module")
def first_alert_dict(pipeline_results):
    a = pipeline_results["alerts"][0]
    return {
        "alert_id": a.alert_id,
        "risk_score": a.risk_score,
        "severity": a.severity,
        "total_amount": a.total_amount,
        "txn_count": a.txn_count,
        "account_count": a.account_count,
        "nodes": [vars(n) for n in a.nodes],
        "edges": [vars(e) for e in a.edges],
        "reason_codes": a.reason_codes,
        "shared_devices": a.shared_devices,
        "shared_ips": a.shared_ips,
        "gnn_score": a.gnn_score,
        "explanation": a.explanation or {},
    }


# ── SHAP Explainer Tests ─────────────────────────────────────────────────────

class TestSHAPExplainer:

    def test_compute_shap_values_returns_results(self, first_alert_dict):
        from backend.explainability.shap_explainer import compute_shap_values
        results = compute_shap_values(first_alert_dict)
        assert len(results) > 0

    def test_shap_result_has_required_fields(self, first_alert_dict):
        from backend.explainability.shap_explainer import compute_shap_values
        results = compute_shap_values(first_alert_dict)
        for r in results:
            assert r.account_id
            assert isinstance(r.base_value, float)
            assert len(r.shap_values) > 0
            assert 0 <= r.predicted_probability <= 1
            assert r.method in ("kernel_shap", "manual_decomposition")

    def test_shap_feature_values_have_descriptions(self, first_alert_dict):
        from backend.explainability.shap_explainer import compute_shap_values
        results = compute_shap_values(first_alert_dict)
        for r in results:
            for sv in r.shap_values:
                assert sv.feature
                assert sv.description

    def test_shap_to_dict_serializable(self, first_alert_dict):
        from backend.explainability.shap_explainer import compute_shap_values
        import json
        results = compute_shap_values(first_alert_dict)
        for r in results:
            d = r.to_dict()
            json.dumps(d)  # must not raise

    def test_waterfall_chart_format(self, first_alert_dict):
        from backend.explainability.shap_explainer import compute_shap_values, format_for_waterfall_chart
        results = compute_shap_values(first_alert_dict)
        if results:
            chart = format_for_waterfall_chart(results[0])
            assert "waterfall" in chart
            assert len(chart["waterfall"]) >= 3  # base + features + total
            assert chart["waterfall"][0]["type"] == "base"
            assert chart["waterfall"][-1]["type"] == "total"

    def test_empty_alert_returns_empty(self):
        from backend.explainability.shap_explainer import compute_shap_values
        results = compute_shap_values({"nodes": [], "edges": []})
        assert results == []


# ── Narrative Generator Tests ─────────────────────────────────────────────────

class TestNarrativeGenerator:

    def test_generates_narrative(self, first_alert_dict):
        from backend.explainability.narrative_generator import generate_narrative
        narrative = generate_narrative(first_alert_dict)
        assert narrative.alert_id == first_alert_dict["alert_id"]

    def test_executive_brief_not_empty(self, first_alert_dict):
        from backend.explainability.narrative_generator import generate_narrative
        narrative = generate_narrative(first_alert_dict)
        assert len(narrative.executive_brief) > 50

    def test_detailed_narrative_has_paragraphs(self, first_alert_dict):
        from backend.explainability.narrative_generator import generate_narrative
        narrative = generate_narrative(first_alert_dict)
        assert len(narrative.detailed_narrative) > 100
        assert "\n\n" in narrative.detailed_narrative

    def test_regulatory_summary_mentions_rbi(self, first_alert_dict):
        from backend.explainability.narrative_generator import generate_narrative
        narrative = generate_narrative(first_alert_dict)
        assert "RBI" in narrative.regulatory_summary
        assert "PMLA" in narrative.regulatory_summary

    def test_key_findings_populated(self, first_alert_dict):
        from backend.explainability.narrative_generator import generate_narrative
        narrative = generate_narrative(first_alert_dict)
        assert len(narrative.key_findings) >= 1

    def test_recommended_actions_by_severity(self, first_alert_dict):
        from backend.explainability.narrative_generator import generate_narrative
        narrative = generate_narrative(first_alert_dict)
        assert len(narrative.recommended_actions) >= 2

    def test_narrative_to_dict_serializable(self, first_alert_dict):
        from backend.explainability.narrative_generator import generate_narrative
        import json
        narrative = generate_narrative(first_alert_dict)
        d = narrative.to_dict()
        json.dumps(d)  # must not raise

    def test_narrative_with_classification(self, first_alert_dict):
        from backend.explainability.narrative_generator import generate_narrative
        classification = {
            "classification": "COMPLICIT",
            "reasoning": "Device sharing and new account age indicate coordinated operation.",
        }
        narrative = generate_narrative(first_alert_dict, classification)
        assert narrative.mule_type == "COMPLICIT"
        assert "COMPLICIT" in narrative.detailed_narrative


# ── Mule Classifier Tests ────────────────────────────────────────────────────

class TestMuleClassifier:

    def test_classify_single_account(self, first_alert_dict, pipeline_results):
        from backend.detection.mule_classifier import classify_mule_type
        node = first_alert_dict["nodes"][0]
        txns = pipeline_results["dataset"]["transactions"]
        result = classify_mule_type(node, txns)
        assert result.classification in ("COMPLICIT", "EXPLOITED", "UNKNOWN")
        assert 0 <= result.confidence <= 1
        assert result.account_id == node["account_id"]

    def test_classify_cluster(self, first_alert_dict, pipeline_results):
        from backend.detection.mule_classifier import classify_cluster
        txns = pipeline_results["dataset"]["transactions"]
        result = classify_cluster(first_alert_dict, txns)
        assert "cluster_classification" in result
        assert result["cluster_classification"] in ("COMPLICIT", "EXPLOITED", "MIXED")
        assert "account_classifications" in result
        assert len(result["account_classifications"]) > 0
        assert "summary" in result
        assert result["summary"]["total"] > 0

    def test_young_account_flags_complicit(self):
        from backend.detection.mule_classifier import classify_mule_type
        account = {
            "account_id": "TEST_YOUNG",
            "account_age_days": 2,
            "kyc_status": "PENDING",
            "role": "MULE",
        }
        txns = [
            {"from_account": "TEST_YOUNG", "to_account": "X", "amount": 20000, "timestamp": "2024-01-01T02:00:00"},
            {"from_account": "TEST_YOUNG", "to_account": "Y", "amount": 25000, "timestamp": "2024-01-01T03:00:00"},
            {"from_account": "TEST_YOUNG", "to_account": "Z", "amount": 15000, "timestamp": "2024-01-01T04:00:00"},
            {"from_account": "TEST_YOUNG", "to_account": "W", "amount": 30000, "timestamp": "2024-01-01T23:30:00"},
            {"from_account": "TEST_YOUNG", "to_account": "V", "amount": 18000, "timestamp": "2024-01-02T00:15:00"},
            {"from_account": "SRC", "to_account": "TEST_YOUNG", "amount": 120000, "timestamp": "2024-01-01T01:00:00"},
        ]
        result = classify_mule_type(account, txns)
        assert result.classification == "COMPLICIT"

    def test_old_dormant_flags_exploited(self):
        from backend.detection.mule_classifier import classify_mule_type
        account = {
            "account_id": "TEST_OLD",
            "account_age_days": 730,
            "kyc_status": "VERIFIED",
            "role": "MULE",
        }
        txns = [
            {"from_account": "TEST_OLD", "to_account": f"R{i}", "amount": 10000, "timestamp": f"2024-01-01T{10+i}:00:00"}
            for i in range(12)
        ] + [
            {"from_account": "SRC", "to_account": "TEST_OLD", "amount": 130000, "timestamp": "2024-01-01T09:00:00"},
        ]
        result = classify_mule_type(account, txns)
        assert result.classification == "EXPLOITED"

    def test_signals_populated(self, first_alert_dict, pipeline_results):
        from backend.detection.mule_classifier import classify_mule_type
        node = first_alert_dict["nodes"][0]
        txns = pipeline_results["dataset"]["transactions"]
        result = classify_mule_type(node, txns)
        assert len(result.signals) >= 1


# ── Pipeline Integration with New Features ───────────────────────────────────

class TestPipelineIntegration:

    def test_alerts_have_narrative(self, pipeline_results):
        for a in pipeline_results["alerts"]:
            assert a.narrative is not None, f"Alert {a.alert_id} missing narrative"
            assert "executive_brief" in a.narrative

    def test_alerts_have_mule_classification(self, pipeline_results):
        for a in pipeline_results["alerts"]:
            assert a.mule_classification is not None, f"Alert {a.alert_id} missing classification"
            assert "cluster_classification" in a.mule_classification

    def test_r20_rule_exists(self):
        engine = RuleEngine()
        rule_codes = [code for code, _, _ in engine.RULES]
        assert "R20" in rule_codes

    def test_alerts_have_explanation(self, pipeline_results):
        for a in pipeline_results["alerts"]:
            assert a.explanation is not None


# ── Explainer (existing) Integration ─────────────────────────────────────────

class TestExplainer:

    def test_explain_alert_produces_full_explanation(self, first_alert_dict):
        from backend.explainability.explainer import explain_alert
        exp = explain_alert(first_alert_dict)
        assert exp.alert_id == first_alert_dict["alert_id"]
        assert len(exp.score_breakdown) > 0
        assert len(exp.score_narrative) > 0
        assert len(exp.recommendation) > 0

    def test_explanation_to_dict(self, first_alert_dict):
        from backend.explainability.explainer import explain_alert
        import json
        exp = explain_alert(first_alert_dict)
        d = exp.to_dict()
        json.dumps(d)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
