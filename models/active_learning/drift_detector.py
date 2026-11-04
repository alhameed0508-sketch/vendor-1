"""
Distribution Drift Detector
=============================
ADWIN-inspired sliding-window drift detection for risk score distributions.
Tracks risk score distribution over time; flags when the recent mean
diverges from the historical mean by more than a configurable threshold.

Returns DriftResult with recommendation: RETRAIN_RECOMMENDED or NO_ACTION.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SIZE = 200
DEFAULT_DRIFT_THRESHOLD = 0.15


@dataclass(frozen=True)
class DriftResult:
    is_drifting: bool
    historical_mean: float
    recent_mean: float
    divergence: float
    recommendation: str  # "RETRAIN_RECOMMENDED" | "NO_ACTION"
    window_size: int
    sample_count: int


class DriftDetector:
    """Sliding-window ADWIN-inspired drift detection for risk scores.

    Tracks risk score distribution; flags when recent mean diverges
    from historical mean by more than the configured threshold.
    """

    def __init__(
        self,
        window_size: int = DEFAULT_WINDOW_SIZE,
        drift_threshold: float = DEFAULT_DRIFT_THRESHOLD,
    ):
        self._window_size = window_size
        self._drift_threshold = drift_threshold
        self._scores: deque = deque(maxlen=window_size * 2)

    def add_score(self, score: float) -> None:
        """Add a risk score observation."""
        self._scores.append(max(0.0, min(1.0, score)))

    def add_scores(self, scores: List[float]) -> None:
        """Add multiple risk score observations."""
        for s in scores:
            self.add_score(s)

    def check_drift(self) -> DriftResult:
        """Check if the risk score distribution has drifted.

        Splits the window into historical (first half) and recent (second half),
        then compares means.
        """
        scores = list(self._scores)
        n = len(scores)

        if n < 20:
            return DriftResult(
                is_drifting=False,
                historical_mean=0.0,
                recent_mean=0.0,
                divergence=0.0,
                recommendation="NO_ACTION",
                window_size=self._window_size,
                sample_count=n,
            )

        # Split into historical and recent windows
        split = n // 2
        historical = scores[:split]
        recent = scores[split:]

        hist_mean = sum(historical) / len(historical)
        recent_mean = sum(recent) / len(recent)
        divergence = abs(recent_mean - hist_mean)

        is_drifting = divergence > self._drift_threshold

        if is_drifting:
            logger.warning(
                "Distribution drift detected: historical_mean=%.3f, recent_mean=%.3f, divergence=%.3f (threshold=%.3f)",
                hist_mean,
                recent_mean,
                divergence,
                self._drift_threshold,
            )

        return DriftResult(
            is_drifting=is_drifting,
            historical_mean=round(hist_mean, 4),
            recent_mean=round(recent_mean, 4),
            divergence=round(divergence, 4),
            recommendation="RETRAIN_RECOMMENDED" if is_drifting else "NO_ACTION",
            window_size=self._window_size,
            sample_count=n,
        )

    def reset(self) -> None:
        """Clear all observations."""
        self._scores.clear()

    @property
    def sample_count(self) -> int:
        return len(self._scores)
