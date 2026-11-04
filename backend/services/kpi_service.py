"""
KPI service — business logic for KPI computation.
"""

from datetime import datetime, timezone
from typing import Dict

from core.config import get_settings
from repositories.kpi_repository import KPIRepository

# Alert statuses where an investigator confirmed the mule network.
CONFIRMED_STATUSES = frozenset({"RESOLVED", "STR_FILED", "SUSPICION_CONFIRMED_ESCALATED"})
ALERT_SCAN_LIMIT = 10_000


class KPIService:
    """KPI computation and formatting."""

    def __init__(self, kpi_repo: KPIRepository, alert_repo=None):
        self._repo = kpi_repo
        self._alert_repo = alert_repo

    def _amounts_by_outcome(self) -> Dict[str, float]:
        """Flagged rupees split by investigator outcome; empty without an alert repo."""
        alerts = self._alert_repo.find_all(limit=ALERT_SCAN_LIMIT) if self._alert_repo else []
        totals = {"verified": 0.0, "false_positive": 0.0, "awaiting": 0.0}
        for a in alerts:
            status, amount = a.get("status"), a.get("total_amount", 0) or 0
            if status in CONFIRMED_STATUSES:
                totals["verified"] += amount
            elif status == "FALSE_POSITIVE":
                totals["false_positive"] += amount
            else:
                totals["awaiting"] += amount
        return totals

    def get_kpis(self) -> Dict:
        """Return enriched KPI snapshot."""
        k = self._repo.get()
        hourly_cost = get_settings().analyst_hourly_cost_inr
        outcome = self._amounts_by_outcome()
        return {
            **k,
            # Flagged = money in alerted clusters, unverified. Prevented counts only confirmed alerts.
            "fraud_flagged_inr": k["fraud_prevented_inr"],
            "fraud_prevented_verified_inr": outcome["verified"],
            "false_positive_inr": outcome["false_positive"],
            "awaiting_review_inr": outcome["awaiting"],
            "manpower_saved_lakh": round(k["hours_saved"] * hourly_cost / 100000, 2),
            "fraud_prevented_crore": round(k["fraud_prevented_inr"] / 10_000_000, 2),
            # These require measured production baselines; do not fabricate
            # values from synthetic or demonstration data.
            "false_positive_reduction_pct": None,
            "avg_investigation_time_min": None,
            "roi_assumptions": {
                "analyst_hourly_cost_inr": hourly_cost,
                "financial_values_are_estimates": True,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
