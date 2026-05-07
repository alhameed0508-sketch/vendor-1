"""
KPI service — business logic for KPI computation.
"""

from datetime import datetime
from typing import Dict

from repositories.kpi_repository import KPIRepository


class KPIService:
    """KPI computation and formatting."""

    def __init__(self, kpi_repo: KPIRepository):
        self._repo = kpi_repo

    def get_kpis(self) -> Dict:
        """Return enriched KPI snapshot."""
        k = self._repo.get()
        return {
            **k,
            "manpower_saved_lakh": round(k["hours_saved"] * 500 / 100000, 2),
            "fraud_prevented_crore": round(k["fraud_prevented_inr"] / 10_000_000, 2),
            "false_positive_reduction_pct": 40,
            "avg_investigation_time_min": 45,
            "timestamp": datetime.utcnow().isoformat(),
        }
