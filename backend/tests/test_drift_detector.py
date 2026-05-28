"""Tests for distribution drift detector."""
import pytest
from models.active_learning.drift_detector import (
    DriftDetector,
    DriftResult,
    DEFAULT_DRIFT_THRESHOLD,
)


class TestDriftResult:
    def test_frozen(self):
        result = DriftResult(
            is_drifting=False, historical_mean=0.5, recent_mean=0.5,
            divergence=0.0, recommendation="NO_ACTION",
            window_size=200, sample_count=100,
        )
        with pytest.raises(AttributeError):
            result.is_drifting = True


class TestDriftDetector:
    def test_no_drift_with_stable_scores(self):
        detector = DriftDetector(window_size=50)
        for _ in range(100):
            detector.add_score(0.5)
        result = detector.check_drift()
        assert not result.is_drifting
        assert result.recommendation == "NO_ACTION"

    def test_drift_with_shifted_distribution(self):
        detector = DriftDetector(window_size=50, drift_threshold=0.15)
        # Historical: low scores
        for _ in range(50):
            detector.add_score(0.3)
        # Recent: high scores (drift)
        for _ in range(50):
            detector.add_score(0.7)
        result = detector.check_drift()
        assert result.is_drifting
        assert result.recommendation == "RETRAIN_RECOMMENDED"
        assert result.divergence > 0.15

    def test_insufficient_data(self):
        detector = DriftDetector()
        for _ in range(10):
            detector.add_score(0.5)
        result = detector.check_drift()
        assert not result.is_drifting
        assert result.sample_count == 10

    def test_add_scores_batch(self):
        detector = DriftDetector(window_size=50)
        detector.add_scores([0.3] * 50 + [0.8] * 50)
        result = detector.check_drift()
        assert result.is_drifting

    def test_reset(self):
        detector = DriftDetector()
        detector.add_scores([0.5] * 100)
        assert detector.sample_count == 100
        detector.reset()
        assert detector.sample_count == 0

    def test_score_clamping(self):
        detector = DriftDetector(window_size=50)
        detector.add_score(-0.5)
        detector.add_score(1.5)
        scores = list(detector._scores)
        assert scores[0] == 0.0
        assert scores[1] == 1.0

    def test_window_size_limit(self):
        detector = DriftDetector(window_size=10)
        for i in range(100):
            detector.add_score(0.5)
        assert detector.sample_count == 20  # maxlen = window_size * 2


class TestGradualDrift:
    def test_gradual_drift_detected(self):
        detector = DriftDetector(window_size=50, drift_threshold=0.10)
        # Gradually increasing scores
        for i in range(100):
            detector.add_score(0.2 + 0.006 * i)
        result = detector.check_drift()
        # Should detect drift since first half avg ~0.35, second half avg ~0.65
        assert result.is_drifting

    def test_no_drift_with_noise(self):
        import random
        random.seed(42)
        detector = DriftDetector(window_size=100)
        for _ in range(200):
            detector.add_score(0.5 + random.gauss(0, 0.05))
        result = detector.check_drift()
        # Small noise should not trigger drift
        assert not result.is_drifting
