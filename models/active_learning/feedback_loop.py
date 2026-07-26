"""
MuleCatch Active Learning Module
==================================
Records investigator feedback and triggers model refinement.
Closes the human-in-the-loop cycle.

Feedback types:
  - TRUE_POSITIVE  : confirmed mule cluster -> reinforce detection rules
  - FALSE_POSITIVE : benign cluster -> tighten scoring thresholds
  - PARTIAL        : some accounts are mules, others are not
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_FEEDBACK_STORE_PATH = (
    Path(__file__).parent.parent.parent / "data" / "feedback_log.jsonl"
)


@dataclass(frozen=True)
class ThresholdConfig:
    """All tunable active-learning parameters in one place."""

    base_smurf_threshold: float = 0.55
    base_suspicion_threshold: float = 0.50
    fp_raise_bound: float = 0.30
    fp_lower_bound: float = 0.10
    raise_delta: float = 0.05
    lower_delta: float = -0.03
    recent_window: int = 20
    min_feedback_for_adjustment: int = 5
    retrain_batch_size: int = 20


@dataclass
class FeedbackRecord:
    feedback_id: str
    alert_id: str
    cluster_id: Optional[str]
    investigator_id: str
    is_true_positive: bool
    false_positive_accounts: List[str] = field(default_factory=list)
    true_positive_accounts: List[str] = field(default_factory=list)
    notes: str = ""
    confidence_weight: float = 1.0
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()


class FeedbackStore:
    """Persists investigator feedback for active learning."""

    def __init__(
        self,
        path: Optional[Path] = None,
        config: Optional[ThresholdConfig] = None,
    ):
        self.path = Path(path) if path else DEFAULT_FEEDBACK_STORE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._config = config or ThresholdConfig()

    def save(self, record: FeedbackRecord):
        with open(self.path, "a") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def load_all(self) -> List[FeedbackRecord]:
        if not self.path.exists():
            return []
        records = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(FeedbackRecord(**json.loads(line)))
        return records

    def false_positive_rate(self) -> float:
        records = self.load_all()
        if not records:
            return 0.0
        fp = sum(1 for r in records if not r.is_true_positive)
        return fp / len(records)

    def get_threshold_adjustment(self) -> float:
        """
        Returns a score delta to apply to detection thresholds
        based on recent feedback. Negative = tighten threshold.
        Uses confidence_weight for weighted feedback.
        """
        cfg = self._config
        records = self.load_all()
        if len(records) < cfg.min_feedback_for_adjustment:
            return 0.0
        recent = records[-cfg.recent_window:]

        total_weight = sum(getattr(r, 'confidence_weight', 1.0) for r in recent)
        if total_weight == 0:
            return 0.0
        fp_weight = sum(
            getattr(r, 'confidence_weight', 1.0)
            for r in recent if not r.is_true_positive
        )
        fp_rate = fp_weight / total_weight

        if fp_rate > cfg.fp_raise_bound:
            return cfg.raise_delta
        elif fp_rate < cfg.fp_lower_bound:
            return cfg.lower_delta
        return 0.0


def get_adjusted_thresholds(
    store: Optional[FeedbackStore] = None,
    config: Optional[ThresholdConfig] = None,
) -> Dict:
    """Returns recommended detection thresholds based on accumulated feedback."""
    cfg = config or ThresholdConfig()
    if store is None:
        store = FeedbackStore(config=cfg)
    delta = store.get_threshold_adjustment()
    return {
        "smurf_flag_threshold": round(cfg.base_smurf_threshold + delta, 3),
        "cluster_suspicion_threshold": round(cfg.base_suspicion_threshold + delta, 3),
        "threshold_delta": delta,
        "false_positive_rate": round(store.false_positive_rate(), 3),
        "total_feedback": len(store.load_all()),
    }


class ActiveLearningEngine:
    """
    Processes feedback batches and emits retraining signals.
    In production, this would trigger a GNN retraining job.
    """

    def __init__(
        self,
        store: Optional[FeedbackStore] = None,
        config: Optional[ThresholdConfig] = None,
    ):
        self._config = config or ThresholdConfig()
        self.store = store or FeedbackStore(config=self._config)

    def record_feedback(
        self,
        alert_id: str,
        cluster_id: Optional[str],
        investigator_id: str,
        is_true_positive: bool,
        notes: str = "",
        false_positive_accounts: List[str] = None,
        true_positive_accounts: List[str] = None,
    ) -> FeedbackRecord:
        import uuid
        record = FeedbackRecord(
            feedback_id=f"FB_{uuid.uuid4().hex[:8].upper()}",
            alert_id=alert_id,
            cluster_id=cluster_id,
            investigator_id=investigator_id,
            is_true_positive=is_true_positive,
            false_positive_accounts=false_positive_accounts or [],
            true_positive_accounts=true_positive_accounts or [],
            notes=notes,
        )
        self.store.save(record)
        return record

    def get_retraining_summary(self) -> Dict:
        records = self.store.load_all()
        return {
            "total_feedback": len(records),
            "true_positives": sum(1 for r in records if r.is_true_positive),
            "false_positives": sum(1 for r in records if not r.is_true_positive),
            "false_positive_rate": round(self.store.false_positive_rate(), 3),
            "recommended_threshold_delta": self.store.get_threshold_adjustment(),
            "retraining_recommended": len(records) >= self._config.retrain_batch_size,
        }

    def should_retrain(self) -> bool:
        records = self.store.load_all()
        batch = self._config.retrain_batch_size
        return len(records) > 0 and len(records) % batch == 0

    @staticmethod
    def get_uncertain_alerts(alerts: List[Dict], k: int = 10) -> List[Dict]:
        """Uncertainty sampling: prioritize alerts near decision boundary.

        Alerts with risk_score closest to 0.5 are most uncertain and
        benefit most from investigator feedback.
        """
        scored = [
            (abs(a.get("risk_score", 0.5) - 0.5), a)
            for a in alerts
        ]
        scored.sort(key=lambda x: x[0])
        return [a for _, a in scored[:k]]


if __name__ == "__main__":
    engine = ActiveLearningEngine()
    for i in range(5):
        fb = engine.record_feedback(
            alert_id=f"ALT_TEST_{i:03d}",
            cluster_id=f"CLU_{i:03d}",
            investigator_id="inv_001",
            is_true_positive=i % 5 != 0,
            notes=f"Test feedback {i}",
        )
        print(f"Recorded: {fb.feedback_id}")
    summary = engine.get_retraining_summary()
    print(f"\nRetraining summary: {summary}")
