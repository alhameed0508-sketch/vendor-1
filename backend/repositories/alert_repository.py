"""
Alert repository — data access layer for alerts.
Delegates to PersistenceLayer; no business logic here.
"""

from typing import Dict, List, Optional

from graph_engine.persistence import PersistenceLayer


class AlertRepository:
    """Encapsulates alert data access behind a consistent interface."""

    def __init__(self, persistence: PersistenceLayer):
        self._persistence = persistence

    def find_all(
        self,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Fetch alerts with optional server-side filtering."""
        return self._persistence.get_alerts(
            severity=severity, status=status, limit=limit
        )

    def find_by_id(self, alert_id: str) -> Optional[Dict]:
        """Fetch a single alert by ID."""
        return self._persistence.get_alert(alert_id)

    def store_batch(self, alerts: List[Dict]) -> None:
        """Persist a batch of alert dicts."""
        self._persistence.store_alerts(alerts)

    def update(
        self,
        alert_id: str,
        status: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[Dict]:
        """Update an alert's status/notes. Returns updated alert or None."""
        return self._persistence.update_alert(alert_id, status=status, notes=notes)
