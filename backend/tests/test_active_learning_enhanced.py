"""Tests for enhanced active learning (uncertainty sampling)."""
import pytest
from models.active_learning.feedback_loop import (
    ActiveLearningEngine,
    FeedbackStore,
    FeedbackRecord,
)
from pathlib import Path
import tempfile


@pytest.fixture
def engine(tmp_path):
    store = FeedbackStore(path=tmp_path / "test_feedback.jsonl")
    eng = ActiveLearningEngine()
    eng.store = store
    return eng


class TestUncertaintySampling:
    def test_uncertain_alerts_near_boundary(self):
        alerts = [
            {"alert_id": "A1", "risk_score": 0.49},
            {"alert_id": "A2", "risk_score": 0.90},
            {"alert_id": "A3", "risk_score": 0.51},
            {"alert_id": "A4", "risk_score": 0.10},
            {"alert_id": "A5", "risk_score": 0.50},
        ]
        result = ActiveLearningEngine.get_uncertain_alerts(alerts, k=3)
        assert len(result) == 3
        # Most uncertain (closest to 0.5) should be first
        ids = [a["alert_id"] for a in result]
        assert "A5" in ids
        assert "A1" in ids
        assert "A3" in ids

    def test_uncertain_alerts_fewer_than_k(self):
        alerts = [{"alert_id": "A1", "risk_score": 0.5}]
        result = ActiveLearningEngine.get_uncertain_alerts(alerts, k=10)
        assert len(result) == 1

    def test_empty_alerts(self):
        result = ActiveLearningEngine.get_uncertain_alerts([], k=5)
        assert result == []


class TestConfidenceWeight:
    def test_feedback_record_default_weight(self):
        record = FeedbackRecord(
            feedback_id="FB_001",
            alert_id="ALT_001",
            cluster_id=None,
            investigator_id="inv_001",
            is_true_positive=True,
        )
        assert record.confidence_weight == 1.0

    def test_feedback_record_custom_weight(self):
        record = FeedbackRecord(
            feedback_id="FB_001",
            alert_id="ALT_001",
            cluster_id=None,
            investigator_id="inv_001",
            is_true_positive=True,
            confidence_weight=0.7,
        )
        assert record.confidence_weight == 0.7


class TestWeightedThreshold:
    def test_weighted_threshold_with_all_fp(self, engine):
        for i in range(10):
            engine.record_feedback(
                alert_id=f"ALT_{i}",
                cluster_id=None,
                investigator_id="inv",
                is_true_positive=False,
            )
        delta = engine.store.get_threshold_adjustment()
        assert delta > 0  # Should raise threshold

    def test_weighted_threshold_with_all_tp(self, engine):
        for i in range(10):
            engine.record_feedback(
                alert_id=f"ALT_{i}",
                cluster_id=None,
                investigator_id="inv",
                is_true_positive=True,
            )
        delta = engine.store.get_threshold_adjustment()
        assert delta < 0  # Should lower threshold
