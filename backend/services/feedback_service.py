"""
Feedback service — investigator feedback and active learning loop.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from core.exceptions import NotFoundError
from repositories.alert_repository import AlertRepository
from repositories.kpi_repository import KPIRepository
from services.audit_service import AuditService

from models.active_learning.feedback_loop import (
    ActiveLearningEngine,
    FeedbackStore,
    ThresholdConfig,
)


class FeedbackService:
    """Business logic for feedback submission and retraining triggers."""

    def __init__(
        self,
        feedback_engine: ActiveLearningEngine,
        feedback_store: FeedbackStore,
        alert_repo: AlertRepository,
        kpi_repo: KPIRepository,
        audit_service: AuditService,
        config: Optional[ThresholdConfig] = None,
    ):
        self._engine = feedback_engine
        self._store = feedback_store
        self._alert_repo = alert_repo
        self._kpi_repo = kpi_repo
        self._audit = audit_service
        self._config = config or ThresholdConfig()

    def submit_feedback(
        self,
        alert_id: str,
        is_true_positive: bool,
        investigator_id: str,
        notes: str,
        user_id: str,
    ) -> Dict:
        """Record investigator feedback and update alert/KPIs."""
        alert = self._alert_repo.find_by_id(alert_id)
        if not alert:
            raise NotFoundError("Alert", alert_id)

        cluster_id = alert.get("cluster_id") if isinstance(alert, dict) else None
        fb = self._engine.record_feedback(
            alert_id=alert_id,
            cluster_id=cluster_id,
            investigator_id=investigator_id,
            is_true_positive=is_true_positive,
            notes=notes,
        )

        if not is_true_positive:
            self._kpi_repo.increment("false_positives_avoided")
            self._alert_repo.update(alert_id, status="FALSE_POSITIVE")

        self._audit.log(
            "FEEDBACK",
            user_id,
            alert_id,
            f"is_true_positive={is_true_positive}",
        )

        return {
            "accepted": True,
            "feedback_id": fb.feedback_id,
            "message": "Feedback recorded. Model will be updated in next cycle.",
            "alert_id": alert_id,
            "retraining_recommended": self._engine.should_retrain(),
        }

    def get_stats(self) -> Dict:
        """Feedback statistics for the ROI dashboard."""
        summary = self._engine.get_retraining_summary()
        return {
            "total_feedback": summary["total_feedback"],
            "true_positives": summary["true_positives"],
            "false_positives": summary["false_positives"],
            "false_positive_rate": summary["false_positive_rate"],
            "recommended_threshold_delta": summary["recommended_threshold_delta"],
            "retraining_recommended": summary["retraining_recommended"],
            "current_smurf_threshold": self._config.base_smurf_threshold + self._store.get_threshold_adjustment(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_retrain_info(self) -> Dict:
        """Get retraining summary and threshold delta."""
        summary = self._engine.get_retraining_summary()
        delta = self._store.get_threshold_adjustment()
        return {
            "summary": summary,
            "delta": delta,
            "new_threshold": round(self._config.base_smurf_threshold + delta, 3),
        }
