"""
KPI repository — wraps PersistenceLayer KPI operations.
"""

from typing import Dict

from graph_engine.persistence import PersistenceLayer


class KPIRepository:
    """Data access for KPI metrics."""

    def __init__(self, persistence: PersistenceLayer):
        self._persistence = persistence

    def get(self) -> Dict:
        """Return current KPI snapshot (copy)."""
        return self._persistence.get_kpi()

    def update(self, **kwargs) -> None:
        """Update KPI fields."""
        self._persistence.update_kpi(**kwargs)

    def increment(self, key: str, amount: float = 1) -> None:
        """Increment a KPI counter."""
        self._persistence.increment_kpi(key, amount)
