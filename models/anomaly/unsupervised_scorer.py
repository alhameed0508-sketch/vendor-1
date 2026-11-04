"""Cold-start account anomaly scoring backed by PyOD.

This tier does not require mule labels. It applies ECOD to the same normalized
account, transaction, graph-centrality, and behavioral features used by the
supervised lightweight scorer. The result is a supporting signal only: it may
raise an alert's risk, but it never makes an adverse decision by itself.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

import numpy as np

from models.gnn.lightweight_scorer import extract_features

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnomalyPrediction:
    """Explainable per-account unsupervised result."""

    account_id: str
    anomaly_score: float
    is_anomaly: bool
    detector: str = "pyod-ecod"


class UnsupervisedAccountScorer:
    """Score anomalous accounts when enough peer accounts are available."""

    MIN_SAMPLES = 20

    def __init__(self, contamination: float = 0.05):
        self._contamination = min(max(contamination, 0.01), 0.2)

    def score(
        self,
        accounts: List[Dict],
        transactions: List[Dict],
        smurf_scores: Dict | None = None,
        centrality: Dict | None = None,
        baselines: Dict | None = None,
    ) -> Dict[str, AnomalyPrediction]:
        account_ids, matrix = extract_features(
            accounts,
            transactions,
            smurf_scores,
            centrality,
            baselines,
        )
        if len(account_ids) < self.MIN_SAMPLES:
            logger.info(
                "PyOD cold-start tier skipped: %d/%d peer accounts",
                len(account_ids),
                self.MIN_SAMPLES,
            )
            return {}

        try:
            from pyod.models.ecod import ECOD

            detector = ECOD(contamination=self._contamination)
            values = np.asarray(matrix, dtype=float)
            detector.fit(values)
            probabilities = detector.predict_proba(values, method="unify")[:, 1]
            labels = detector.labels_
        except (ImportError, ValueError, RuntimeError) as exc:
            logger.warning("PyOD anomaly scoring unavailable: %s", exc)
            return {}

        return {
            account_id: AnomalyPrediction(
                account_id=account_id,
                anomaly_score=round(float(probability), 4),
                is_anomaly=bool(label),
            )
            for account_id, probability, label in zip(
                account_ids,
                probabilities,
                labels,
            )
        }
