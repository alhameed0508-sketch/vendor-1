"""Tests for rolling mule propensity scorer."""
import time
import pytest
from models.propensity.rolling_scorer import (
    RollingPropensityScorer,
    PropensityRecord,
    WINDOWS,
    WINDOW_WEIGHTS,
    EXTERNAL_WEIGHTS,
)


@pytest.fixture
def scorer():
    return RollingPropensityScorer()


class TestPropensityRecord:
    def test_frozen(self):
        record = PropensityRecord(
            account_id="A", score=0.5, window_scores=(),
            signal_breakdown=(), updated_at=time.time(),
        )
        with pytest.raises(AttributeError):
            record.score = 0.9


class TestWindowWeights:
    def test_weights_sum_to_one(self):
        assert abs(sum(WINDOW_WEIGHTS.values()) - 1.0) < 0.001

    def test_external_weights_bounded(self):
        total = sum(EXTERNAL_WEIGHTS.values())
        assert total <= 0.5  # External should not dominate


class TestRecordTransaction:
    def test_basic_recording(self, scorer):
        scorer.record_transaction("ACC_001", 10000, "REC_001")
        record = scorer.update_score("ACC_001")
        assert record.score >= 0.0
        assert record.account_id == "ACC_001"

    def test_multiple_transactions(self, scorer):
        now = time.time()
        for i in range(10):
            scorer.record_transaction(
                "ACC_001", 5000, f"REC_{i:03d}", timestamp=now - i * 300,
            )
        record = scorer.update_score("ACC_001")
        assert record.score > 0.0
        assert len(record.window_scores) == len(WINDOWS)


class TestWindowScoring:
    def test_high_velocity_increases_score(self, scorer):
        now = time.time()
        # Many transactions in short window
        for i in range(20):
            scorer.record_transaction("FAST", 1000, f"R{i}", now - i * 60)
        fast = scorer.update_score("FAST")

        scorer.record_transaction("SLOW", 1000, "R0", now - 3600)
        slow = scorer.update_score("SLOW")

        assert fast.score > slow.score

    def test_pass_through_scoring(self, scorer):
        now = time.time()
        # High pass-through: incoming roughly equals outgoing
        scorer.record_transaction("MULE", 50000, "SOURCE", now - 100, is_incoming=True)
        scorer.record_transaction("MULE", 48000, "DEST", now - 50)
        record = scorer.update_score("MULE")
        assert record.score > 0.0


class TestExternalBoosts:
    def test_smurf_boost(self, scorer):
        scorer.record_transaction("A", 1000, "B")
        base = scorer.update_score("A")
        boosted = scorer.update_score("A", smurf_score=0.9)
        assert boosted.score > base.score

    def test_all_boosts(self, scorer):
        scorer.record_transaction("A", 1000, "B")
        record = scorer.update_score(
            "A",
            smurf_score=0.8,
            device_trust=0.7,
            semantics_score=0.6,
            baseline_deviation=0.5,
        )
        assert record.score > 0.0
        breakdown = dict(record.signal_breakdown)
        assert "smurf_boost" in breakdown
        assert "device_trust_boost" in breakdown

    def test_score_capped_at_one(self, scorer):
        now = time.time()
        for i in range(30):
            scorer.record_transaction("MAX", 50000, f"R{i}", now - i * 60)
        record = scorer.update_score("MAX", smurf_score=1.0, device_trust=1.0)
        assert record.score <= 1.0


class TestGetScore:
    def test_get_nonexistent(self, scorer):
        assert scorer.get_score("UNKNOWN") is None

    def test_get_after_record(self, scorer):
        scorer.record_transaction("A", 1000, "B")
        scorer.update_score("A")
        record = scorer.get_score("A")
        assert record is not None
        assert record.account_id == "A"


class TestTopRisk:
    def test_top_risk_ordering(self, scorer):
        now = time.time()
        # High risk account
        for i in range(15):
            scorer.record_transaction("HIGH", 50000, f"R{i}", now - i * 60)
        scorer.update_score("HIGH", smurf_score=0.9)

        # Low risk account
        scorer.record_transaction("LOW", 1000, "R0", now - 3600)
        scorer.update_score("LOW")

        top = scorer.get_top_risk(limit=10)
        assert len(top) == 2
        assert top[0].account_id == "HIGH"
        assert top[0].score > top[1].score
