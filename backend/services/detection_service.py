"""
Detection service — orchestrates dataset generation and pipeline execution.
"""

from typing import Dict, List

from core.config import get_settings
from detection.pipeline import Alert, DetectionPipeline
from repositories.alert_repository import AlertRepository
from repositories.dataset_repository import DatasetRepository
from repositories.kpi_repository import KPIRepository

from models.active_learning.feedback_loop import FeedbackStore

# -- Detection KPI constants --------------------------------------------------
# Estimated analyst hours saved per automated alert
HOURS_SAVED_PER_ALERT = 3.0
# Risk score threshold above which an alert warrants SAR filing
SAR_PROBABILITY_THRESHOLD = 0.7


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
        "anomaly_score": a.anomaly_score,
        "model_version": a.model_version,
        "rule_version": a.rule_version,
        "genai_triage": a.genai_triage,
        "nodes": [vars(n) for n in a.nodes],
        "edges": [vars(e) for e in a.edges],
        "explanation": a.explanation,
        "narrative": a.narrative,
        "mule_classification": a.mule_classification,
        "shap_explanation": a.shap_explanation,
        "regulatory_report": a.regulatory_report,
        "rank_score": a.rank_score,
        "evidence_share": a.evidence_share,
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

    def ensure_alerts(self, skip_demo_statuses: bool = False) -> List[Dict]:
        """Lazy-init: return existing alerts or run detection pipeline.

        Args:
            skip_demo_statuses: If True, skip demo status assignment even in
                demo mode. Used when processing real uploaded data.
        """
        existing = self._alert_repo.find_all(limit=200)
        if existing:
            return existing

        dataset = self.get_or_generate_dataset()

        # Apply feedback-adjusted thresholds
        settings = get_settings()
        threshold_delta = self._feedback_store.get_threshold_adjustment()
        if threshold_delta != 0.0:
            self._pipeline._smurf_threshold = settings.smurf_flag_threshold + threshold_delta

        alerts = self._pipeline.run(dataset["transactions"], dataset["accounts"])
        alert_dicts = [alert_to_dict(a) for a in alerts]

        settings = get_settings()
        if settings.demo_mode and not skip_demo_statuses:
            # Assign diverse statuses for realistic demo
            alert_dicts = sorted(alert_dicts, key=lambda a: -a["rank_score"])
            demo_statuses = [
                "OPEN",
                "OPEN",
                "UNDER_REVIEW",
                "OPEN",
                "RESOLVED",
                "UNDER_REVIEW",
                "OPEN",
                "FALSE_POSITIVE",
            ]
            enriched = []
            for i, ad in enumerate(alert_dicts):
                updates = {}
                if i < len(demo_statuses):
                    updates["status"] = demo_statuses[i]
                status = updates.get("status", ad["status"])
                if status == "UNDER_REVIEW":
                    updates["investigator_notes"] = "Reviewing cluster topology and transaction velocity patterns."
                elif status == "RESOLVED":
                    updates["investigator_notes"] = "Confirmed mule network. STR filed with FIU."
                elif status == "FALSE_POSITIVE":
                    updates["investigator_notes"] = "Legitimate payroll batch. Accounts verified by branch manager."
                enriched.append({**ad, **updates})
        else:
            # Production or skip_demo: all alerts start as OPEN
            enriched = alert_dicts

        self._alert_repo.store_batch(enriched)

        # Update KPIs
        self._kpi_repo.update(
            total_alerts=len(alerts),
            fraud_prevented_inr=sum(a.total_amount for a in alerts),
            hours_saved=len(alerts) * HOURS_SAVED_PER_ALERT,
            strs_filed=len([a for a in alerts if a.risk_score > SAR_PROBABILITY_THRESHOLD]),
        )

        # Update detection breakdown counters in PG if available
        self._update_detection_breakdown(enriched)

        return enriched

    def _update_detection_breakdown(self, alerts: List[Dict]) -> None:
        """Increment detection_breakdown and monthly_trends in PG if available."""
        try:
            from api.deps import _get_pg_engine

            engine = _get_pg_engine()
            if engine is None:
                return

            from datetime import datetime, timezone

            from sqlalchemy.dialects.postgresql import insert as pg_insert

            from backend.infra.database.postgres import (
                detection_breakdown,
                monthly_trends,
            )

            # Count patterns across all alerts
            pattern_counts: Dict[str, int] = {}
            for alert in alerts:
                for code in alert.get("reason_codes", []):
                    pattern_counts[code] = pattern_counts.get(code, 0) + 1

            with engine.connect() as conn:
                # Upsert detection breakdown
                for pattern, count in pattern_counts.items():
                    stmt = (
                        pg_insert(detection_breakdown)
                        .values(pattern=pattern, count=count)
                        .on_conflict_do_update(
                            index_elements=["pattern"],
                            set_={"count": count},
                        )
                    )
                    conn.execute(stmt)

                # Upsert monthly trends
                now = datetime.now(timezone.utc)
                month_key = now.strftime("%b")
                total_prevented = sum(a.get("total_amount", 0) for a in alerts) / 100_000  # Convert to lakh
                stmt = (
                    pg_insert(monthly_trends)
                    .values(
                        month=month_key,
                        alerts=len(alerts),
                        prevented=round(total_prevented, 1),
                        hours=len(alerts) * HOURS_SAVED_PER_ALERT,
                    )
                    .on_conflict_do_update(
                        index_elements=["month"],
                        set_={
                            "alerts": len(alerts),
                            "prevented": round(total_prevented, 1),
                            "hours": len(alerts) * HOURS_SAVED_PER_ALERT,
                        },
                    )
                )
                conn.execute(stmt)
                conn.commit()
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Failed to update detection breakdown: %s", exc)

    def run_fresh_detection(self) -> None:
        """Clear state and re-run detection. Used as a background task."""
        self._dataset_repo.clear()
        self.ensure_alerts()

    def retrain(self, threshold_delta: float) -> None:
        """Background retrain with adjusted thresholds."""
        settings = get_settings()
        self._dataset_repo.clear()
        if threshold_delta != 0.0:
            self._pipeline._smurf_threshold = settings.smurf_flag_threshold + threshold_delta
        dataset = self.get_or_generate_dataset()
        alerts = self._pipeline.run(dataset["transactions"], dataset["accounts"])
        alert_dicts = [alert_to_dict(a) for a in alerts]
        self._alert_repo.store_batch(alert_dicts)
