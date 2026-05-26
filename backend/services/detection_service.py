"""
Detection service — orchestrates dataset generation and pipeline execution.
"""

from typing import Dict, List

from detection.pipeline import DetectionPipeline, Alert
from models.active_learning.feedback_loop import FeedbackStore
from repositories.alert_repository import AlertRepository
from repositories.dataset_repository import DatasetRepository
from repositories.kpi_repository import KPIRepository
from core.config import get_settings


def alert_to_dict(a: Alert) -> Dict:
    """Convert a pipeline Alert object to a serializable dict."""
    return {
        "alert_id": a.alert_id,
        "cluster_id": a.cluster_id,
        "severity": a.severity,
        "confidence": a.confidence,
        "risk_score": a.risk_score,
        "total_amount": a.total_amount,
        "txn_count": a.txn_count,
        "account_count": a.account_count,
        "reason_codes": a.reason_codes,
        "shared_devices": a.shared_devices,
        "shared_ips": a.shared_ips,
        "created_at": a.created_at,
        "status": a.status,
        "investigator_notes": a.investigator_notes,
        "gnn_score": a.gnn_score,
        "genai_triage": a.genai_triage,
        "nodes": [vars(n) for n in a.nodes],
        "edges": [vars(e) for e in a.edges],
        "explanation": a.explanation,
        "narrative": a.narrative,
        "mule_classification": a.mule_classification,
    }


class DetectionService:
    """Pipeline orchestration: dataset generation + detection run."""

    def __init__(
        self,
        pipeline: DetectionPipeline,
        feedback_store: FeedbackStore,
        alert_repo: AlertRepository,
        dataset_repo: DatasetRepository,
        kpi_repo: KPIRepository,
    ):
        self._pipeline = pipeline
        self._feedback_store = feedback_store
        self._alert_repo = alert_repo
        self._dataset_repo = dataset_repo
        self._kpi_repo = kpi_repo

    def get_or_generate_dataset(self) -> Dict:
        """Return cached dataset or generate a new one.
        In production, never generate synthetic data — data comes from Kafka.
        """
        ds = self._dataset_repo.get()
        if ds is None:
            settings = get_settings()
            if not settings.demo_mode:
                # Production should never generate synthetic data
                return {"transactions": [], "accounts": []}
            from data.synthetic.generator import build_full_dataset
            ds = build_full_dataset(num_clusters=8, num_legit_accounts=60)
            self._dataset_repo.set(ds)
        return ds

    def ensure_alerts(self) -> List[Dict]:
        """Lazy-init: return existing alerts or run detection pipeline."""
        existing = self._alert_repo.find_all(limit=200)
        if existing:
            return existing

        dataset = self.get_or_generate_dataset()

        # Apply feedback-adjusted thresholds
        threshold_delta = self._feedback_store.get_threshold_adjustment()
        if threshold_delta != 0.0:
            self._pipeline._smurf_threshold = 0.55 + threshold_delta

        alerts = self._pipeline.run(dataset["transactions"], dataset["accounts"])
        alert_dicts = [alert_to_dict(a) for a in alerts]

        settings = get_settings()
        if settings.demo_mode:
            # Assign diverse statuses for realistic demo
            alert_dicts.sort(key=lambda a: -a["risk_score"])
            demo_statuses = [
                "OPEN", "OPEN", "UNDER_REVIEW", "OPEN", "RESOLVED",
                "UNDER_REVIEW", "OPEN", "FALSE_POSITIVE",
            ]
            enriched = []
            for i, ad in enumerate(alert_dicts):
                updates = {}
                if i < len(demo_statuses):
                    updates["status"] = demo_statuses[i]
                status = updates.get("status", ad["status"])
                if status == "UNDER_REVIEW":
                    updates["investigator_notes"] = (
                        "Reviewing cluster topology and transaction velocity patterns."
                    )
                elif status == "RESOLVED":
                    updates["investigator_notes"] = (
                        "Confirmed mule network. STR filed with FIU."
                    )
                elif status == "FALSE_POSITIVE":
                    updates["investigator_notes"] = (
                        "Legitimate payroll batch. Accounts verified by branch manager."
                    )
                enriched.append({**ad, **updates})
        else:
            # Production: no demo statuses, all alerts start as OPEN
            enriched = alert_dicts

        self._alert_repo.store_batch(enriched)

        # Update KPIs
        self._kpi_repo.update(
            total_alerts=len(alerts),
            fraud_prevented_inr=sum(a.total_amount for a in alerts),
            hours_saved=len(alerts) * 3.0,
            strs_filed=len([a for a in alerts if a.risk_score > 0.7]),
        )
        return enriched

    def run_fresh_detection(self) -> None:
        """Clear state and re-run detection. Used as a background task."""
        self._dataset_repo.clear()
        self.ensure_alerts()

    def retrain(self, threshold_delta: float) -> None:
        """Background retrain with adjusted thresholds."""
        self._dataset_repo.clear()
        if threshold_delta != 0.0:
            self._pipeline._smurf_threshold = 0.55 + threshold_delta
        dataset = self.get_or_generate_dataset()
        alerts = self._pipeline.run(dataset["transactions"], dataset["accounts"])
        alert_dicts = [alert_to_dict(a) for a in alerts]
        self._alert_repo.store_batch(alert_dicts)
