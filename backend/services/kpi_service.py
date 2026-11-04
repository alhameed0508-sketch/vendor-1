"""
KPI service — business logic for KPI computation.
"""

from datetime import datetime, timezone
from typing import Dict

from core.config import get_settings
from repositories.kpi_repository import KPIRepository


class KPIService:
    """KPI computation and formatting."""

    def __init__(self, kpi_repo: KPIRepository):
        self._repo = kpi_repo

    def get_kpis(self) -> Dict:
        """Return enriched KPI snapshot."""
        k = self._repo.get()
        hourly_cost = get_settings().analyst_hourly_cost_inr
        return {
            **k,
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
